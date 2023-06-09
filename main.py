from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm
from flask_gravatar import Gravatar
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL
import secrets


app = Flask(__name__)
secret_key = secrets.token_hex(16)
app.config['SECRET_KEY'] = secret_key
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)


##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = r'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.relationship("User", back_populates="posts")
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = db.relationship('Comment', back_populates="parent_post", lazy=True, cascade="all, delete-orphan")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author = db.relationship("User", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    posts = db.relationship('BlogPost', back_populates="author", lazy=True)
    comments = db.relationship('Comment', back_populates="author", lazy=True)

    @staticmethod
    def get(user_id):
        return User.query.get(int(user_id))


class RegisterForm(FlaskForm):
    email = StringField("Email:", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class LoginForm(FlaskForm):
    email = StringField("Email:", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class CommentForm(FlaskForm):
    body = CKEditorField('Comment', validators=[DataRequired()])
    submit = SubmitField("Submit Post")


with app.app_context():
    db.create_all()


@app.context_processor
def inject_user():
    return {'user': current_user}


def admin_only(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            abort(403)
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


def authenticate(email, password):
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        return user


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=['POST', 'GET'])
def register():
    form = RegisterForm()
    if request.method == "POST":
        if not User.query.filter_by(email=request.form["email"]).first():
            name = request.form["name"]
            new_user = User(
                email=request.form["email"],
                name=request.form["name"],
                password=generate_password_hash(request.form["password"], salt_length=8)
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(authenticate(request.form["email"], request.form["password"]))
            return redirect(url_for('get_all_posts'))
        else:
            flash("Email already registered!", 'error')
    return render_template("register.html", form=form)


@app.route('/login', methods=['POST', 'GET'])
def login():
    form = LoginForm()
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = authenticate(email, password)
        if user:
            login_user(user)
            name = user.name
            return redirect(url_for('get_all_posts'))
        else:
            flash('Invalid email or password', 'error')
    return render_template("login.html", form=form)


@app.route("/post/<int:post_id>", methods=['POST', 'GET'])
def show_post(post_id):
    form = CommentForm()
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash('You need to login or register to comment!', 'error')
            return redirect(url_for('login'))
        else:
            new_comment = Comment(
                text=form.body.data,
                author=current_user,
                parent_post=db.session.query(BlogPost).get(post_id),
                post_id=post_id,
                author_id=current_user.id
            )
            db.session.add(new_comment)
            db.session.commit()
    requested_post = BlogPost.query.get(post_id)
    comments = requested_post.comments
    return render_template("post.html", post=requested_post, form=form, comments=comments)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")



@app.route("/new-post", methods=['POST', 'GET'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
            author_id=current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['POST', 'GET'])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=current_user,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>", methods=['POST', 'GET'])
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route('/logout', methods=['POST', 'GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
