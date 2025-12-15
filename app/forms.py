from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from .models import User  # Относительный импорт

class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', 
                          validators=[DataRequired(), 
                                     Length(min=3, max=64)])
    password = PasswordField('Пароль', 
                            validators=[DataRequired(), 
                                       Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', 
                                    validators=[DataRequired(), 
                                               EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Это имя пользователя уже занято.')

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', 
                          validators=[DataRequired()])
    password = PasswordField('Пароль', 
                            validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class UpdateProfileForm(FlaskForm):
    username = StringField('Имя пользователя', 
                          validators=[DataRequired(), 
                                     Length(min=3, max=64)])

    submit = SubmitField('Обновить')
