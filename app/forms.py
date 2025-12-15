from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional, Regexp
from .models import User

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

class CheckoutForm(FlaskForm):
    address = TextAreaField('Адрес доставки', 
                          validators=[DataRequired(), 
                                     Length(min=10, max=500)])
    phone = StringField('Телефон', 
                       validators=[Optional(),
                                  Length(min=5, max=20),
                                  Regexp(r'^[\d\s\+\-\(\)]+$', 
                                         message='Некорректный номер телефона')])
    comment = TextAreaField('Комментарий к заказу',
                          validators=[Optional(),
                                     Length(max=500)])
    submit = SubmitField('Оформить заказ')