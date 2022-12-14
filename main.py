from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, ContactForm
from flask_gravatar import Gravatar
from functools import wraps
from datetime import datetime
import smtplib
import os
from dotenv import load_dotenv

load_dotenv("/Users/jenniferlau/Python/EnvironmentVariables/.env")

MY_EMAIL = os.getenv("TestEmail")
EMAIL_PASSWORD = os.getenv("EmailPassword")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

current_year = datetime.now().year

def send_email(name, email, message):

    email_message = f"Subject:New Message\n\nName: {name}\nEmail: {email}\nMessage:{message}"
    with smtplib.SMTP("smtp.gmail.com", port="587") as connection:
        connection.starttls()
        connection.login(user=MY_EMAIL, password=EMAIL_PASSWORD)
        connection.sendmail(
            from_addr=MY_EMAIL,
            to_addrs=MY_EMAIL,
            msg=email_message.encode("utf-8")
        )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")

    # This will act like a List of Comments objects attached to each User
    # The "comment_author" refers to property in the Comments class
    comments = relationship("Comment", back_populates="comment_author")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the tablename of Users
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # author property now references the User object, "posts" refers to posts property in User class
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    photo_url = db.Column(db.String(250))
    attribution_url = db.Column(db.String(250))
    photographer = db.Column(db.String(100))

    # This will act as a List of Comments objects attached to each BlogPost
    comments = relationship("Comment", back_populates="parent_post")

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key to link to Users table
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # comment_author property now references User object, "comments" refers to property in User class
    comment_author = relationship("User", back_populates="comments")


    # Create a Foreign Key to link to BlogPosts table
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    # parent_post property now references BlogPost object, "comments" refers to property in BlogPost class
    parent_post = relationship("BlogPost", back_populates="comments")

    comment = db.Column(db.Text, nullable=False)

# Line below only required once, when creating DB.
# db.create_all()

# Decorator functions

def admin_only(fn):
    @wraps(fn)
    def decorated_function(*args, **kwargs):
        # if user_id is not 1 (admin), return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # otherwise, continue with route function
        else:
            return fn(*args, **kwargs)

    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user, year=current_year)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        # Check if user already exists
        if User.query.filter_by(email=form.email.data).first():
            flash("You've already signed up with that email, login instead!")
            return redirect(url_for("login"))

        hashed_salted_pw = generate_password_hash(
            form.password.data,
            method="pbkdf2:sha256",
            salt_length=8)
        new_user = User(
            email=form.email.data,
            password=hashed_salted_pw,
            name=form.name.data)
        db.session.add(new_user)
        db.session.commit()

        # Log in and authenticate user after adding details to database.
        login_user(new_user)

        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form, year=current_year)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Find user by email
        user = User.query.filter_by(email=email).first()

        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for("login"))

        # Check stored pw hash against entered pw hash
        elif not check_password_hash(user.password, password):
            # pw incorrect
            flash("Password incorrect, please try again.")
            return redirect(url_for("login"))
        else:
            # Email and pw both correct
            login_user(user)

            return redirect(url_for("get_all_posts"))

    return render_template("login.html", form=form, year=current_year)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)

    if form.validate_on_submit():
        # Make sure user is logged in
        if not current_user.is_authenticated:
            flash("You need to login or register to leave a comment")
            return redirect(url_for("login"))

        new_comment = Comment(
            comment_author=current_user,
            comment=form.comment.data,
            parent_post=requested_post
        )

        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", static=url_for("static", filename=""), post=requested_post, current_user=current_user, form=form, year=current_year)


@app.route("/about")
def about():
    return render_template("about.html", year=current_year)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        message = form.message.data

        send_email(name, email, message)
        flash(f"Thanks for your message, {name}!")
        return redirect(url_for("contact"))
    return render_template("contact.html", form=form, year=current_year)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            unsplash_url=form.unsplash_url.data,
            photographer=form.photographer.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, year=current_year)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
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

    return render_template("make-post.html", form=edit_form, year=current_year)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
