from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, FloatField
from wtforms.validators import DataRequired, Optional, Length


class CarForm(FlaskForm):
    manufacturer = StringField('Производитель', validators=[Optional(), Length(max=100)])
    name = StringField('Модель', validators=[DataRequired(), Length(max=150)])
    year = IntegerField('Год', validators=[Optional()])
    vin = StringField('VIN', validators=[Optional(), Length(max=100)])
    plate = StringField('Номер', validators=[Optional(), Length(max=50)])


class PartForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(max=200)])
    manufacturer_id = SelectField('Производитель', coerce=int, validators=[Optional()])
    type_id = SelectField('Тип', coerce=int, validators=[Optional()])
    system_id = SelectField('Система', coerce=int, validators=[Optional()])
    article = StringField('Артикул', validators=[Optional(), Length(max=100)])
    original_article = StringField('Ориг. арт', validators=[Optional(), Length(max=100)])
