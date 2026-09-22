from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import csv
import io
from datetime import datetime

app = Flask(__name__)

# Configuration: use DATABASE_URL if set, otherwise SQLite local file
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Use absolute path for SQLite to avoid issues with working directory changes
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cars.db')
    DATABASE_URL = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Secret key for WTForms CSRF — override via environment variable in production
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from models import (Car, Part, Manufacturer, PartType, CarSystem, ExpenseType,
                    Expense, Fuel, PartPurchase, Service, ServiceTask,
                    ServiceHistory, ServiceHistoryTask)
from forms import CarForm, PartForm


@app.context_processor
def global_car_context():
    selected_car_id = session.get('selected_car_id')
    filter_by_car = session.get('filter_by_car', False)
    filter_by_date = session.get('filter_by_date', False)
    selected_car = db.session.get(Car, selected_car_id) if selected_car_id else None
    return {'global_cars': Car.query.order_by(Car.manufacturer, Car.name).all(),
            'selected_car_id': selected_car_id, 'selected_car': selected_car,
            'filter_by_car': filter_by_car, 'filter_by_date': filter_by_date,
            'date_from': session.get('date_from', ''), 'date_to': session.get('date_to', '')}


@app.route('/set-global-car', methods=['POST'])
def set_global_car():
    selected_car_id = request.form.get('global_car_id')
    if selected_car_id is not None:
        session['selected_car_id'] = int(selected_car_id) if selected_car_id else None
        session['filter_by_car'] = request.form.get('filter_by_car') == 'on'
    if 'filter_by_date' in request.form:
        session['filter_by_date'] = '1' in request.form.getlist('filter_by_date')
        session['date_from'] = request.form.get('date_from', '').strip()
        session['date_to'] = request.form.get('date_to', '').strip()
        preset = request.form.get('preset')
        if preset in {'1m', '3m', '6m', '1y'}:
            from datetime import date, timedelta
            days = {'1m': 31, '3m': 93, '6m': 186, '1y': 365}[preset]
            session['filter_by_date'] = True
            session['date_from'] = (date.today() - timedelta(days=days)).isoformat()
            session['date_to'] = date.today().isoformat()
    return redirect(request.form.get('next') or url_for('index'))


def selected_car_filter(query, model):
    if session.get('filter_by_car') and session.get('selected_car_id'):
        return query.filter(model.car_id == session['selected_car_id'])
    return query


def selected_date_filter(query, model, field_name):
    if not session.get('filter_by_date'):
        return query
    date_from = session.get('date_from')
    date_to = session.get('date_to')
    column = getattr(model, field_name)
    if date_from:
        query = query.filter(column >= date_from)
    if date_to:
        query = query.filter(column <= date_to)
    return query

@app.route("/")
def index():
    return redirect(url_for('service_history_index')) # return redirect(url_for('directories', kind='cars'))

@app.route("/cars/add", methods=["POST"])
def add_car():
    manufacturer = request.form.get("manufacturer")
    name = request.form.get("name")
    year = request.form.get("year") or None
    vin = request.form.get("vin")
    plate = request.form.get("plate")

    car = Car(manufacturer=manufacturer, name=name, year=year or None, vin=vin, plate_number=plate)
    db.session.add(car)
    db.session.commit()
    return redirect(url_for("index"))


@app.route('/directories/cars', methods=['GET', 'POST'])
def cars_directory():
    if request.method == 'POST':
        manufacturer = request.form.get('manufacturer', '').strip()
        name = request.form.get('name', '').strip()
        year = request.form.get('year') or None
        if not name:
            flash('Модель автомобиля обязательна', 'danger')
        else:
            try:
                car = Car(manufacturer=manufacturer or None, name=name,
                          year=_as_int(year, 'Год') if year else None,
                          vin=request.form.get('vin', '').strip() or None,
                          plate_number=request.form.get('plate', '').strip() or None)
                db.session.add(car)
                db.session.commit()
                return redirect(url_for('cars_directory'))
            except Exception as error:
                db.session.rollback()
                flash('Не удалось добавить автомобиль: ' + str(error), 'danger')
    cars = Car.query.order_by(Car.manufacturer, Car.name).all()
    return render_template('cars_directory.html', cars=cars)


@app.route("/cars/edit/<int:car_id>", methods=["GET", "POST"])
def edit_car(car_id):
    car = Car.query.get_or_404(car_id)
    if request.method == 'POST':
        try:
            car.manufacturer = request.form.get('manufacturer', '').strip() or None
            car.name = request.form.get('name', '').strip()
            car.year = _as_int(request.form.get('year'), 'Год') if request.form.get('year') else None
            car.vin = request.form.get('vin', '').strip() or None
            car.plate_number = request.form.get('plate', '').strip() or None
            if not car.name:
                raise ValueError('Модель автомобиля обязательна')
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
            return redirect(url_for('cars_directory'))
        db.session.commit()
        return redirect(url_for('cars_directory'))
    return render_template('car_form.html', form=CarForm(obj=car), car=car)

@app.route("/cars/delete/<int:car_id>")
def delete_car(car_id):
    car = Car.query.get_or_404(car_id)
    db.session.delete(car)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/parts")
def parts_index():
    parts = Part.query.all()
    cars = Car.query.order_by(Car.manufacturer, Car.name).all()
    service_histories = ServiceHistory.query.order_by(ServiceHistory.service_date.desc()).all()
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    part_types = PartType.query.order_by(PartType.name).all()
    systems = CarSystem.query.order_by(CarSystem.name).all()
    # provide a PartForm to the template (for CSRF + validation)
    form = PartForm()
    form.manufacturer_id.choices = [(0, '---')] + [(m.id, m.name) for m in manufacturers]
    form.type_id.choices = [(0, '---')] + [(t.id, t.name) for t in part_types]
    form.system_id.choices = [(0, '---')] + [(s.id, s.name) for s in systems]
    edit_part_id = request.args.get('edit', type=int)
    return render_template("parts.html", parts=parts, cars=cars, service_histories=service_histories, manufacturers=manufacturers, part_types=part_types, systems=systems, form=form, edit_part_id=edit_part_id)


@app.route("/parts/add", methods=["POST"])
def add_part():
    form = PartForm()
    # populate choices
    form.manufacturer_id.choices = [(0, '---')] + [(m.id, m.name) for m in Manufacturer.query.order_by(Manufacturer.name).all()]
    form.type_id.choices = [(0, '---')] + [(t.id, t.name) for t in PartType.query.order_by(PartType.name).all()]
    form.system_id.choices = [(0, '---')] + [(s.id, s.name) for s in CarSystem.query.order_by(CarSystem.name).all()]

    if form.validate_on_submit():
        manufacturer_id = form.manufacturer_id.data or None
        type_id = form.type_id.data or None
        system_id = form.system_id.data or None
        part = Part(name=form.name.data,
                    manufacturer_id=manufacturer_id,
                    type_id=type_id,
                    system_id=system_id,
                    article=form.article.data,
                    original_article=form.original_article.data)
        db.session.add(part)
        db.session.commit()
        return redirect(url_for("parts_index"))
    # if not POST or validation failed, render parts page with form errors
    parts = Part.query.all()
    manufacturers = Manufacturer.query.order_by(Manufacturer.name).all()
    part_types = PartType.query.order_by(PartType.name).all()
    systems = CarSystem.query.order_by(CarSystem.name).all()
    return render_template("parts.html", parts=parts, manufacturers=manufacturers, part_types=part_types, systems=systems, form=form)


@app.route('/parts/edit/<int:part_id>', methods=['GET', 'POST'])
def edit_part(part_id):
    part = Part.query.get_or_404(part_id)
    form = PartForm(obj=part)
    form.manufacturer_id.choices = [(0, '---')] + [(m.id, m.name) for m in Manufacturer.query.order_by(Manufacturer.name).all()]
    form.type_id.choices = [(0, '---')] + [(t.id, t.name) for t in PartType.query.order_by(PartType.name).all()]
    form.system_id.choices = [(0, '---')] + [(s.id, s.name) for s in CarSystem.query.order_by(CarSystem.name).all()]

    if request.method == 'POST':
        part.name = request.form.get('name', '').strip()
        part.manufacturer_id = int(request.form.get('manufacturer_id') or 0) or None
        part.type_id = int(request.form.get('type_id') or 0) or None
        part.system_id = int(request.form.get('system_id') or 0) or None
        part.article = request.form.get('article', '').strip() or None
        part.original_article = request.form.get('original_article', '').strip() or None
        if not part.name:
            flash('Название запчасти обязательно', 'danger')
            return redirect(url_for('parts_index'))
        db.session.commit()
        return redirect(url_for('parts_index'))

    return render_template('part_form.html', form=form, part=part)


@app.route("/parts/delete/<int:part_id>")
def delete_part(part_id):
    part = Part.query.get_or_404(part_id)
    db.session.delete(part)
    db.session.commit()
    return redirect(url_for("parts_index"))


def _as_int(value, label):
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Поле «{label}» должно быть целым числом")


def _as_float(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Поле «{label}» должно быть числом")


def _operation_context(title, action, records, form_fields, cars, parts=None,
                      expense_types=None, services=None, tasks=None,
                      form_record=None, edit_mode=False, total=0, service_histories=None):
    return render_template(
           "operations.html", title=title, action=action, records=records,
        form_fields=form_fields, cars=cars, parts=parts or [],
        expense_types=expense_types or [], services=services or [],
        tasks=tasks or [], form_record=form_record, edit_mode=edit_mode, total=total,
        service_histories=service_histories or [])


@app.route('/expenses', methods=['GET', 'POST'])
def expenses_index():
    cars = Car.query.order_by(Car.name).all()
    expense_types = ExpenseType.query.order_by(ExpenseType.name).all()
    if request.method == 'POST':
        try:
            item = Expense(
                car_id=_as_int(request.form.get('car_id'), 'Автомобиль'),
                expense_type_id=_as_int(request.form.get('expense_type_id'), 'Тип расхода'),
                amount=_as_float(request.form.get('amount'), 'Сумма'),
                expense_date=request.form.get('expense_date'),
                comment=request.form.get('comment'))
            if not item.car_id or not item.expense_type_id or not item.expense_date:
                raise ValueError('Заполните автомобиль, тип расхода и дату')
            db.session.add(item)
            db.session.commit()
            return redirect(url_for('expenses_index'))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
    query = db.session.query(Expense, Car, ExpenseType).join(Car, Expense.car_id == Car.id).join(
        ExpenseType, Expense.expense_type_id == ExpenseType.id)
    records = selected_date_filter(selected_car_filter(query, Expense), Expense, 'expense_date').order_by(Expense.expense_date.desc()).all()
    return _operation_context('Расходы', url_for('expenses_index'), records,
                              ['car', 'expense_type', 'amount', 'expense_date', 'comment'], cars,
                              expense_types=expense_types)


@app.route('/expenses/<int:expense_id>/edit', methods=['POST'])
def edit_expense(expense_id):
    item = db.session.get(Expense, expense_id)
    if not item:
        return 'Record not found', 404
    try:
        item.car_id = _as_int(request.form.get('car_id'), 'Автомобиль')
        item.expense_type_id = _as_int(request.form.get('expense_type_id'), 'Тип расхода')
        item.amount = _as_float(request.form.get('amount'), 'Сумма')
        item.expense_date = request.form.get('expense_date')
        item.comment = request.form.get('comment')
        if not item.car_id or not item.expense_type_id or not item.expense_date:
            raise ValueError('Заполните автомобиль, тип расхода и дату')
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'danger')
    return redirect(url_for('expenses_index'))


@app.route('/fuel', methods=['GET', 'POST'])
def fuel_index():
    cars = Car.query.order_by(Car.name).all()
    if request.method == 'POST':
        try:
            item = Fuel(car_id=_as_int(request.form.get('car_id'), 'Автомобиль'),
                        liters=_as_float(request.form.get('liters'), 'Литры'),
                        price=_as_float(request.form.get('price'), 'Цена'),
                        fuel_date=request.form.get('fuel_date'))
            if not item.car_id or not item.fuel_date:
                raise ValueError('Заполните автомобиль и дату')
            db.session.add(item)
            db.session.commit()
            return redirect(url_for('fuel_index'))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
    query = db.session.query(Fuel, Car).outerjoin(Car, Fuel.car_id == Car.id)
    records = selected_date_filter(selected_car_filter(query, Fuel), Fuel, 'fuel_date').order_by(Fuel.fuel_date.desc()).all()
    total = sum((record[0].liters or 0) * (record[0].price or 0) for record in records)
    return _operation_context('Топливо', url_for('fuel_index'), records,
                              ['car', 'liters', 'price', 'fuel_date'], cars, total=total)


@app.route('/fuel/<int:fuel_id>/edit', methods=['POST'])
def edit_fuel(fuel_id):
    item = db.session.get(Fuel, fuel_id)
    if not item:
        return 'Record not found', 404
    try:
        item.car_id = _as_int(request.form.get('car_id'), 'Автомобиль')
        item.liters = _as_float(request.form.get('liters'), 'Литры')
        item.price = _as_float(request.form.get('price'), 'Цена')
        item.fuel_date = request.form.get('fuel_date')
        if not item.car_id or not item.fuel_date:
            raise ValueError('Заполните автомобиль и дату')
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'danger')
    return redirect(url_for('fuel_index'))


@app.route('/purchases', methods=['GET', 'POST'])
def purchases_index():
    cars = Car.query.order_by(Car.name).all()
    parts = Part.query.order_by(Part.name).all()
    service_histories = ServiceHistory.query.order_by(ServiceHistory.service_date.desc()).all()
    if request.method == 'POST':
        try:
            item = PartPurchase(
                car_id=_as_int(request.form.get('car_id'), 'Автомобиль'),
                part_id=_as_int(request.form.get('part_id'), 'Запчасть'),
                purchase_date=request.form.get('purchase_date'),
                quantity=_as_float(request.form.get('quantity'), 'Количество'),
                price=_as_float(request.form.get('price'), 'Цена'),
                service_history_id=_as_int(request.form.get('service_history_id'), 'Использование в ТО'))
            if not item.car_id or not item.part_id or not item.purchase_date:
                raise ValueError('Заполните автомобиль, запчасть и дату')
            db.session.add(item)
            db.session.commit()
            return redirect(url_for('purchases_index'))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
    query = db.session.query(PartPurchase, Car, Part).join(Car, PartPurchase.car_id == Car.id).join(
        Part, PartPurchase.part_id == Part.id).outerjoin(ServiceHistory, PartPurchase.service_history_id == ServiceHistory.id)
    records = selected_date_filter(selected_car_filter(query, PartPurchase), PartPurchase, 'purchase_date').order_by(PartPurchase.purchase_date.desc()).all()
    total = sum(record[0].quantity * record[0].price for record in records)
    return _operation_context('Покупки запчастей', url_for('purchases_index'), records,
                              ['car', 'part', 'purchase_date', 'quantity', 'price'], cars,
                              parts=parts, total=total, service_histories=service_histories)


@app.route('/purchases/<int:purchase_id>/edit', methods=['GET', 'POST'])
def edit_purchase(purchase_id):
    item = db.session.get(PartPurchase, purchase_id)
    if not item:
        return 'Record not found', 404
    cars = Car.query.order_by(Car.name).all()
    parts = Part.query.order_by(Part.name).all()
    service_histories = ServiceHistory.query.order_by(ServiceHistory.service_date.desc()).all()
    if request.method == 'POST':
        try:
            item.car_id = _as_int(request.form.get('car_id'), 'Автомобиль')
            item.part_id = _as_int(request.form.get('part_id'), 'Запчасть')
            item.purchase_date = request.form.get('purchase_date')
            item.quantity = _as_float(request.form.get('quantity'), 'Количество')
            item.price = _as_float(request.form.get('price'), 'Цена')
            item.service_history_id = _as_int(request.form.get('service_history_id'), 'Использование в ТО')
            if not item.car_id or not item.part_id or not item.purchase_date:
                raise ValueError('Заполните автомобиль, запчасть и дату')
            db.session.commit()
            return redirect(url_for('purchases_index'))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
    query = db.session.query(PartPurchase, Car, Part).join(Car, PartPurchase.car_id == Car.id).join(
        Part, PartPurchase.part_id == Part.id).outerjoin(ServiceHistory, PartPurchase.service_history_id == ServiceHistory.id)
    records = selected_date_filter(selected_car_filter(query, PartPurchase), PartPurchase, 'purchase_date').order_by(PartPurchase.purchase_date.desc()).all()
    total = sum(record[0].quantity * record[0].price for record in records)
    return _operation_context('Редактирование покупки', url_for('edit_purchase', purchase_id=item.id), records,
                              ['car', 'part', 'purchase_date', 'quantity', 'price'], cars,
                              parts=parts, form_record=item, edit_mode=True, total=total,
                              service_histories=service_histories)


@app.route('/service-history', methods=['GET', 'POST'])
def service_history_index():
    cars = Car.query.order_by(Car.name).all()
    services = Service.query.order_by(Service.name).all()
    service_tasks = ServiceTask.query.order_by(ServiceTask.name).all()
    if request.method == 'POST':
        try:
            item = ServiceHistory(
                car_id=_as_int(request.form.get('car_id'), 'Автомобиль'),
                service_date=request.form.get('service_date'),
                mileage=_as_int(request.form.get('mileage'), 'Пробег'),
                sto_id=_as_int(request.form.get('sto_id'), 'СТО'),
                description=request.form.get('description'),
                amount=_as_float(request.form.get('amount'), 'Сумма'))
            if not item.car_id or not item.service_date or item.mileage is None:
                raise ValueError('Заполните автомобиль, дату и пробег')
            db.session.add(item)
            db.session.commit()
            for task_id in request.form.getlist('service_task_ids'):
                task_id = _as_int(task_id, 'Стандартная работа')
                if task_id:
                    db.session.add(ServiceHistoryTask(service_history_id=item.id, service_task_id=task_id))
            db.session.commit()
            return redirect(url_for('service_history_index'))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
    query = db.session.query(ServiceHistory, Car, Service).join(Car, ServiceHistory.car_id == Car.id).outerjoin(
        Service, ServiceHistory.sto_id == Service.id)
    records = selected_date_filter(selected_car_filter(query, ServiceHistory), ServiceHistory, 'service_date').order_by(ServiceHistory.service_date.desc()).all()
    total = sum(record[0].amount for record in records)
    return _operation_context('История ТО', url_for('service_history_index'), records,
                              ['car', 'service_date', 'mileage', 'sto', 'description', 'amount'], cars,
                              services=services, tasks=service_tasks, total=total)


@app.route('/api/service-history/<int:history_id>/parts')
def service_history_parts(history_id):
    history = db.session.get(ServiceHistory, history_id)
    if not history:
        return jsonify({'error': 'Record not found'}), 404
    purchases = PartPurchase.query.filter_by(service_history_id=history_id).all()
    return jsonify({'parts': [
        {'name': purchase.part.display_name if purchase.part else str(purchase.part_id),
         'quantity': purchase.quantity, 'price': purchase.price,
         'amount': purchase.quantity * purchase.price}
        for purchase in purchases
    ]})


@app.route('/service-history/<int:history_id>/edit', methods=['POST'])
def edit_service_history(history_id):
    item = db.session.get(ServiceHistory, history_id)
    if not item:
        return 'Record not found', 404
    service_tasks = ServiceTask.query.order_by(ServiceTask.name).all()
    try:
        item.car_id = _as_int(request.form.get('car_id'), 'Автомобиль')
        item.service_date = request.form.get('service_date')
        item.mileage = _as_int(request.form.get('mileage'), 'Пробег')
        item.sto_id = _as_int(request.form.get('sto_id'), 'СТО')
        item.description = request.form.get('description')
        item.amount = _as_float(request.form.get('amount'), 'Сумма')
        if not item.car_id or not item.service_date or item.mileage is None:
            raise ValueError('Заполните автомобиль, дату и пробег')
        db.session.commit()
        ServiceHistoryTask.query.filter_by(service_history_id=item.id).delete()
        for task_id in request.form.getlist('service_task_ids'):
            task_id = _as_int(task_id, 'Стандартная работа')
            if task_id:
                db.session.add(ServiceHistoryTask(service_history_id=item.id, service_task_id=task_id))
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'danger')
    return redirect(url_for('service_history_index'))


@app.route('/records/<entity>/<int:record_id>/delete')
def delete_record(entity, record_id):
    models = {'expense': Expense, 'fuel': Fuel, 'purchase': PartPurchase, 'service-history': ServiceHistory}
    endpoints = {'expense': 'expenses_index', 'fuel': 'fuel_index', 'purchase': 'purchases_index',
                 'service-history': 'service_history_index'}
    model = models.get(entity)
    if not model:
        return 'Unknown entity', 404
    item = db.session.get(model, record_id)
    if not item:
        return 'Record not found', 404
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for(endpoints[entity]))


REFERENCE_MODELS = {
    'manufacturers': ('Производители', Manufacturer),
    'part-types': ('Типы запчастей', PartType),
    'car-systems': ('Системы автомобиля', CarSystem),
    'expense-types': ('Типы расходов', ExpenseType),
    'services': ('СТО', Service),
}


@app.route('/directories/service-tasks', methods=['GET', 'POST'])
def service_tasks_directory():
    cars = Car.query.order_by(Car.manufacturer, Car.name).all()
    if request.method == 'POST':
        try:
            car_id = _as_int(request.form.get('car_id'), 'Автомобиль')
            abbr = request.form.get('abbr', '').strip().upper()
            name = request.form.get('name', '').strip()
            interval_km = _as_int(request.form.get('interval_km'), 'Интервал, км') if request.form.get('interval_km') else None
            interval_months = _as_int(request.form.get('interval_months'), 'Интервал, месяцы') if request.form.get('interval_months') else None
            if not car_id or not abbr or not name:
                raise ValueError('Заполните автомобиль, аббревиатуру и название')
            db.session.add(ServiceTask(car_id=car_id, abbr=abbr, name=name,
                                       interval_km=interval_km, interval_months=interval_months))
            db.session.commit()
            return redirect(url_for('service_tasks_directory'))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
    query = ServiceTask.query
    tasks = selected_car_filter(query, ServiceTask).order_by(ServiceTask.name).all()
    return render_template('service_tasks_directory.html', tasks=tasks, cars=cars)


@app.route('/directories/service-tasks/<int:task_id>/edit', methods=['POST'])
def edit_service_task(task_id):
    task = db.session.get(ServiceTask, task_id)
    if not task:
        return 'Record not found', 404
    try:
        task.car_id = _as_int(request.form.get('car_id'), 'Автомобиль')
        task.abbr = request.form.get('abbr', '').strip().upper()
        task.name = request.form.get('name', '').strip()
        task.interval_km = _as_int(request.form.get('interval_km'), 'Интервал, км') if request.form.get('interval_km') else None
        task.interval_months = _as_int(request.form.get('interval_months'), 'Интервал, месяцы') if request.form.get('interval_months') else None
        if not task.car_id or not task.abbr or not task.name:
            raise ValueError('Заполните автомобиль, аббревиатуру и название')
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'danger')
    return redirect(url_for('service_tasks_directory'))


@app.route('/directories/service-tasks/<int:task_id>/delete')
def delete_service_task(task_id):
    task = db.session.get(ServiceTask, task_id)
    if not task:
        return 'Record not found', 404
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('service_tasks_directory'))


@app.route('/directories/<kind>', methods=['GET', 'POST'])
def directories(kind):
    definition = REFERENCE_MODELS.get(kind)
    if not definition:
        return 'Unknown directory', 404
    title, model = definition
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        country = request.form.get('country', '').strip()
        if not name:
            flash('Название не может быть пустым', 'danger')
        else:
            item = model(name=name)
            if model is Manufacturer:
                item.country = country or None
            db.session.add(item)
            try:
                db.session.commit()
                return redirect(url_for('directories', kind=kind))
            except Exception:
                db.session.rollback()
                flash('Такая запись уже существует', 'danger')
    records = model.query.order_by(model.name).all()
    return render_template('directory.html', title=title, kind=kind, records=records,
                           has_country=model is Manufacturer)


@app.route('/directories/<kind>/<int:record_id>/delete')
def delete_directory(kind, record_id):
    definition = REFERENCE_MODELS.get(kind)
    if not definition:
        return 'Unknown directory', 404
    item = db.session.get(definition[1], record_id)
    if not item:
        return 'Record not found', 404
    db.session.delete(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Запись используется и не может быть удалена', 'danger')
    return redirect(url_for('directories', kind=kind))


@app.route('/directories/<kind>/<int:record_id>/edit', methods=['POST'])
def edit_directory(kind, record_id):
    definition = REFERENCE_MODELS.get(kind)
    if not definition:
        return 'Unknown directory', 404
    item = db.session.get(definition[1], record_id)
    if not item:
        return 'Record not found', 404
    name = request.form.get('name', '').strip()
    if not name:
        flash('Название не может быть пустым', 'danger')
        return redirect(url_for('directories', kind=kind))
    item.name = name
    if definition[1] is Manufacturer:
        item.country = request.form.get('country', '').strip() or None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Такая запись уже существует', 'danger')
    return redirect(url_for('directories', kind=kind))


# ===== CSV Export/Import =====

# Определение конфигурации таблиц для экспорта/импорта
TABLE_CONFIGS = {
    'expenses': {
        'model': Expense,
        'columns': [
            {'db': 'expense_date', 'label': 'Дата', 'type': 'date'},
            {'db': 'car_id', 'label': 'Автомобиль', 'type': 'fk', 'fk_model': Car, 'fk_field': 'plate_number', 'fk_display': lambda c: f"{c.manufacturer} {c.name} - {c.plate_number}"},
            {'db': 'expense_type_id', 'label': 'Тип расхода', 'type': 'fk', 'fk_model': ExpenseType, 'fk_field': 'name', 'fk_display': lambda e: e.name},
            {'db': 'amount', 'label': 'Сумма', 'type': 'float'},
            {'db': 'comment', 'label': 'Комментарий', 'type': 'str'},
        ]
    },
    'fuel': {
        'model': Fuel,
        'columns': [
            {'db': 'fuel_date', 'label': 'Дата заправки', 'type': 'date'},
            {'db': 'car_id', 'label': 'Автомобиль', 'type': 'fk', 'fk_model': Car, 'fk_field': 'plate_number', 'fk_display': lambda c: f"{c.manufacturer} {c.name} - {c.plate_number}"},
            {'db': 'liters', 'label': 'Литры', 'type': 'float'},
            {'db': 'price', 'label': 'Цена', 'type': 'float'},
        ]
    },
    'part_purchases': {
        'model': PartPurchase,
        'columns': [
            {'db': 'purchase_date', 'label': 'Дата покупки', 'type': 'date'},
            {'db': 'car_id', 'label': 'Автомобиль', 'type': 'fk', 'fk_model': Car, 'fk_field': 'plate_number', 'fk_display': lambda c: f"{c.manufacturer} {c.name} - {c.plate_number}"},
            {'db': 'part_id', 'label': 'Запчасть', 'type': 'fk', 'fk_model': Part, 'fk_field': 'article', 'fk_display': lambda p: f"{p.article} {p.name}"},
            {'db': 'quantity', 'label': 'Количество', 'type': 'float'},
            {'db': 'price', 'label': 'Цена', 'type': 'float'},
        ]
    },
    'service_history': {
        'model': ServiceHistory,
        'columns': [
            {'db': 'service_date', 'label': 'Дата', 'type': 'date'},
            {'db': 'car_id', 'label': 'Автомобиль', 'type': 'fk', 'fk_model': Car, 'fk_field': 'plate_number', 'fk_display': lambda c: f"{c.manufacturer} {c.name} - {c.plate_number}"},
            {'db': 'mileage', 'label': 'Пробег', 'type': 'float'},
            {'db': 'sto_id', 'label': 'СТО', 'type': 'fk', 'fk_model': Service, 'fk_field': 'name', 'fk_display': lambda s: s.name},
            {'db': 'amount', 'label': 'Стоимость', 'type': 'float'},
            {'db': 'description', 'label': 'Дополнительно', 'type': 'str'},
        ]
    },
    'parts': {
        'model': Part,
        'columns': [
            {'db': 'article', 'label': 'Артикул', 'type': 'str'},
            {'db': 'original_article', 'label': 'Ориг. артикул', 'type': 'str'},
            {'db': 'name', 'label': 'Наименование', 'type': 'str'},
            {'db': 'manufacturer_id', 'label': 'Производитель', 'type': 'fk', 'fk_model': Manufacturer, 'fk_field': 'name', 'fk_display': lambda m: m.name},
            {'db': 'type_id', 'label': 'Тип', 'type': 'fk', 'fk_model': PartType, 'fk_field': 'name', 'fk_display': lambda t: t.name},
            {'db': 'system_id', 'label': 'Система', 'type': 'fk', 'fk_model': CarSystem, 'fk_field': 'name', 'fk_display': lambda s: s.name},
        ]
    },
    'service_tasks': {
        'model': ServiceTask,
        'columns': [
            {'db': 'car_id', 'label': 'Автомобиль', 'type': 'fk', 'fk_model': Car, 'fk_field': 'plate_number', 'fk_display': lambda c: f"{c.manufacturer} {c.name} - {c.plate_number}"},
            {'db': 'abbr', 'label': 'Аббревиатура', 'type': 'str'},
            {'db': 'name', 'label': 'Название', 'type': 'str'},
            {'db': 'interval_km', 'label': 'Интервал, км', 'type': 'int'},
            {'db': 'interval_months', 'label': 'Интервал, месяцы', 'type': 'int'},
        ]
    },
    'expense_types': {
        'model': ExpenseType,
        'columns': [
            {'db': 'name', 'label': 'Название', 'type': 'str'},
        ],
        'unique_fields': ['name']
    },
    'services': {
        'model': Service,
        'columns': [
            {'db': 'name', 'label': 'Название', 'type': 'str'},
        ],
        'unique_fields': ['name']
    },
    'manufacturers': {
        'model': Manufacturer,
        'columns': [
            {'db': 'name', 'label': 'Название', 'type': 'str'},
            {'db': 'country', 'label': 'Страна', 'type': 'str'},
        ],
        'unique_fields': ['name']
    },
    'part_types': {
        'model': PartType,
        'columns': [
            {'db': 'name', 'label': 'Название', 'type': 'str'},
        ],
        'unique_fields': ['name']
    },
    'car_systems': {
        'model': CarSystem,
        'columns': [
            {'db': 'name', 'label': 'Название', 'type': 'str'},
        ],
        'unique_fields': ['name']
    },
    'cars': {
        'model': Car,
        'columns': [
            {'db': 'manufacturer', 'label': 'Производитель', 'type': 'str'},
            {'db': 'name', 'label': 'Название', 'type': 'str'},
            {'db': 'year', 'label': 'Год', 'type': 'int'},
            {'db': 'vin', 'label': 'VIN', 'type': 'str'},
            {'db': 'plate_number', 'label': 'Гос. номер', 'type': 'str'},
        ]
    },
}


@app.route('/export/<table_name>')
def export_table(table_name):
    """Экспорт активной таблицы в CSV"""
    config = TABLE_CONFIGS.get(table_name)
    if not config:
        flash('Неизвестная таблица', 'danger')
        return redirect(url_for('index'))

    model = config['model']
    columns = config['columns']

    # Получаем данные с учетом фильтров
    query = model.query

    # Применяем фильтр по автомобилю если есть car_id
    if hasattr(model, 'car_id'):
        query = selected_car_filter(query, model)

    # Применяем фильтр по датам если есть поле даты
    date_field = None
    for col in columns:
        if col['type'] == 'date':
            date_field = col['db']
            break
    if date_field:
        query = selected_date_filter(query, model, date_field)

    records = query.all()

    # Создаем CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)

    # Заголовки
    headers = [col['label'] for col in columns]
    writer.writerow(headers)

    # Данные
    for record in records:
        row = []
        for col in columns:
            value = getattr(record, col['db'], '')

            # Обработка FK полей - экспортируем lookup_field
            if col['type'] == 'fk' and value:
                fk_obj = db.session.get(col['fk_model'], value)
                if fk_obj:
                    value = getattr(fk_obj, col['fk_field'], '')
                else:
                    value = ''

            row.append(value if value is not None else '')

        writer.writerow(row)

    # Создаем также шаблон для импорта (пустой CSV с заголовками)
    template_output = io.StringIO()
    template_writer = csv.writer(template_output, delimiter=';', quoting=csv.QUOTE_ALL)
    template_writer.writerow(headers)

    # Возвращаем основной экспорт
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename={table_name}_export.csv'

    return response


@app.route('/export/<table_name>/template')
def export_template(table_name):
    """Экспорт шаблона для импорта (пустой CSV с заголовками)"""
    config = TABLE_CONFIGS.get(table_name)
    if not config:
        flash('Неизвестная таблица', 'danger')
        return redirect(url_for('index'))

    columns = config['columns']

    # Создаем шаблон CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)

    # Только заголовки
    headers = [col['label'] for col in columns]
    writer.writerow(headers)

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    response.headers['Content-Disposition'] = f'attachment; filename={table_name}_template.csv'

    return response


@app.route('/import/<table_name>', methods=['POST'])
def import_table(table_name):
    """Импорт данных из CSV"""
    config = TABLE_CONFIGS.get(table_name)
    if not config:
        flash('Неизвестная таблица', 'danger')
        return redirect(url_for('index'))

    if 'file' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(request.referrer or url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(request.referrer or url_for('index'))

    if not file.filename.endswith('.csv'):
        flash('Только CSV файлы поддерживаются', 'danger')
        return redirect(request.referrer or url_for('index'))

    try:
        # Читаем файл с автоопределением кодировки
        file_bytes = file.stream.read()

        # Пробуем разные кодировки
        content = None
        for encoding in ['utf-8-sig', 'utf-8', 'windows-1251', 'cp1251']:
            try:
                content = file_bytes.decode(encoding)
                break
            except (UnicodeDecodeError, AttributeError):
                continue

        if content is None:
            flash('Не удалось определить кодировку файла', 'danger')
            return redirect(request.referrer or url_for('index'))

        # Нормализуем переводы строк
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        stream = io.StringIO(content, newline='')
        reader = csv.reader(stream, delimiter=';', quotechar='"')

        headers = next(reader)
        # Очищаем заголовки от кавычек и пробелов
        headers = [h.strip().strip('"').strip() for h in headers]
        columns = config['columns']

        # Создаем маппинг label -> column config
        label_to_col = {col['label']: col for col in columns}

        # Проверяем заголовки
        for h in headers:
            if h not in label_to_col:
                flash(f'Неизвестная колонка: {h}', 'danger')
                return redirect(request.referrer or url_for('index'))

        # Импортируем данные
        imported_count = 0
        skipped_count = 0
        for row in reader:
            if not any(row):  # Пропускаем пустые строки
                continue

            record_data = {}

            for value, header in zip(row, headers):
                col = label_to_col[header]
                db_field = col['db']

                if not value or value.strip() == '':
                    record_data[db_field] = None
                    continue

                # Обработка FK полей
                if col['type'] == 'fk':
                    fk_model = col['fk_model']
                    fk_field = col['fk_field']

                    # Ищем существующую запись
                    fk_obj = fk_model.query.filter(getattr(fk_model, fk_field) == value).first()

                    # Если не найдена - создаем автоматически
                    if not fk_obj:
                        fk_obj = fk_model(**{fk_field: value})
                        db.session.add(fk_obj)
                        db.session.flush()  # Получаем ID

                    record_data[db_field] = fk_obj.id

                # Обработка типов данных
                elif col['type'] == 'float':
                    try:
                        record_data[db_field] = float(value)
                    except ValueError:
                        record_data[db_field] = 0.0

                elif col['type'] == 'int':
                    try:
                        record_data[db_field] = int(value)
                    except ValueError:
                        record_data[db_field] = 0

                elif col['type'] == 'date':
                    record_data[db_field] = value

                else:  # str
                    record_data[db_field] = value

            # Проверяем существование записи по уникальным полям
            model = config['model']
            unique_fields = config.get('unique_fields', [])

            existing_record = None
            if unique_fields:
                filters = []
                for field in unique_fields:
                    if field in record_data and record_data[field] is not None:
                        filters.append(getattr(model, field) == record_data[field])

                if filters:
                    query = model.query
                    for f in filters:
                        query = query.filter(f)
                    existing_record = query.first()

            # Если запись существует - пропускаем
            if existing_record:
                skipped_count += 1
                continue

            # Создаем новую запись
            new_record = model(**record_data)
            db.session.add(new_record)
            imported_count += 1

        db.session.commit()

        message = f'Импортировано: {imported_count}'
        if skipped_count > 0:
            message += f', пропущено (уже существуют): {skipped_count}'
        flash(message, 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка импорта: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('index'))


@app.route('/reports/oil-changes')
def report_oil_changes():
    """Отчет о выполненных работах"""
    selected_car_id = session.get('selected_car_id')

    if not selected_car_id:
        return render_template('report_oil_changes.html', car=None, tasks=[], records=[], selected_task_id=None, selected_task=None)

    car = db.session.get(Car, selected_car_id)

    # Получаем все стандартные работы для этого автомобиля
    tasks = ServiceTask.query.filter_by(car_id=selected_car_id).order_by(ServiceTask.abbr).all()

    # Получаем выбранную работу из параметра запроса
    selected_task_id = request.args.get('task_id', type=int)
    selected_task = None
    records = []

    if selected_task_id:
        selected_task = db.session.get(ServiceTask, selected_task_id)

        if selected_task:
            # Получаем все записи истории ТО с этой работой
            service_history_records = db.session.query(ServiceHistory).join(
                ServiceHistoryTask
            ).filter(
                ServiceHistoryTask.service_task_id == selected_task_id,
                ServiceHistory.car_id == selected_car_id
            ).order_by(ServiceHistory.service_date).all()

            # Вычисляем интервалы
            prev_mileage = None
            for record in service_history_records:
                interval = None
                if prev_mileage is not None and record.mileage:
                    interval = record.mileage - prev_mileage

                # Преобразуем дату из строки
                try:
                    service_date = datetime.strptime(record.service_date, '%Y-%m-%d') if isinstance(record.service_date, str) else record.service_date
                except:
                    service_date = record.service_date

                records.append({
                    'service_date': service_date,
                    'mileage': record.mileage,
                    'interval': interval,
                    'service': record.service
                })

                if record.mileage:
                    prev_mileage = record.mileage

    return render_template('report_oil_changes.html',
                          car=car,
                          tasks=tasks,
                          records=records,
                          selected_task_id=selected_task_id,
                          selected_task=selected_task)


@app.route('/reports/general')
def report_general():
    """Общий отчет по автомобилю"""
    from datetime import datetime
    from sqlalchemy import func

    selected_car_id = session.get('selected_car_id')

    if not selected_car_id:
        return render_template('report_general.html', car=None)

    car = db.session.get(Car, selected_car_id)
    generation_date = datetime.now().strftime('%d.%m.%Y')

    # Получаем все стандартные работы для этого автомобиля
    tasks = ServiceTask.query.filter_by(car_id=selected_car_id).order_by(ServiceTask.abbr).all()

    # Получаем выбранную работу из параметра запроса
    selected_task_id = request.args.get('task_id', type=int)
    selected_task = None
    if selected_task_id:
        selected_task = db.session.get(ServiceTask, selected_task_id)

    # Расходы по типам
    expenses_by_type = db.session.query(
        ExpenseType.name,
        func.sum(Expense.amount).label('total')
    ).join(Expense).filter(
        Expense.car_id == selected_car_id
    ).group_by(ExpenseType.name).all()

    expenses_total = sum(item.total for item in expenses_by_type) if expenses_by_type else 0

    # Расходы на сервисы по СТО
    service_by_sto = db.session.query(
        Service.name,
        func.sum(ServiceHistory.amount).label('total')
    ).join(ServiceHistory).filter(
        ServiceHistory.car_id == selected_car_id
    ).group_by(Service.name).all()

    service_total = sum(item.total for item in service_by_sto) if service_by_sto else 0

    # Расходы на топливо
    fuel_total = db.session.query(func.sum(Fuel.liters * Fuel.price)).filter(
        Fuel.car_id == selected_car_id
    ).scalar() or 0

    # Покупки запчастей по типам
    parts_by_type = db.session.query(
        PartType.name,
        func.sum(PartPurchase.quantity * PartPurchase.price).label('total')
    ).join(Part, Part.id == PartPurchase.part_id).join(
        PartType, PartType.id == Part.type_id
    ).filter(
        PartPurchase.car_id == selected_car_id
    ).group_by(PartType.name).all()

    parts_total = sum(item.total for item in parts_by_type) if parts_by_type else 0

    # Итоги
    grand_total = expenses_total + service_total + fuel_total + parts_total

    # Период эксплуатации
    dates = []
    for model in [Expense, Fuel, PartPurchase, ServiceHistory]:
        date_field = {'Expense': 'expense_date', 'Fuel': 'fuel_date',
                      'PartPurchase': 'purchase_date', 'ServiceHistory': 'service_date'}[model.__name__]
        result = db.session.query(
            func.min(getattr(model, date_field)),
            func.max(getattr(model, date_field))
        ).filter(model.car_id == selected_car_id).first()
        if result[0]:
            try:
                date_obj = datetime.strptime(result[0], '%Y-%m-%d') if isinstance(result[0], str) else result[0]
                dates.append(date_obj)
            except:
                pass
        if result[1]:
            try:
                date_obj = datetime.strptime(result[1], '%Y-%m-%d') if isinstance(result[1], str) else result[1]
                dates.append(date_obj)
            except:
                pass

    if dates:
        first_date = min(dates)
        last_date = max(dates)
        operation_period = f"{first_date.strftime('%d.%m.%Y')} - {last_date.strftime('%d.%m.%Y')}"
        ownership_days = (last_date - first_date).days + 1
        cost_per_day = grand_total / ownership_days if ownership_days > 0 else 0
    else:
        operation_period = "Нет данных"
        ownership_days = 0
        cost_per_day = 0

    # Последний пробег
    last_mileage_record = ServiceHistory.query.filter(
        ServiceHistory.car_id == selected_car_id,
        ServiceHistory.mileage.isnot(None)
    ).order_by(ServiceHistory.service_date.desc()).first()

    last_mileage = last_mileage_record.mileage if last_mileage_record else 0
    cost_per_km = grand_total / last_mileage if last_mileage > 0 else 0

    # Данные для графика
    mileage_records = ServiceHistory.query.filter(
        ServiceHistory.car_id == selected_car_id,
        ServiceHistory.mileage.isnot(None)
    ).order_by(ServiceHistory.service_date).all()

    mileage_data = []
    for r in mileage_records:
        try:
            date_str = r.service_date if isinstance(r.service_date, str) else r.service_date.strftime('%Y-%m-%d')
            mileage_data.append({'x': date_str, 'y': r.mileage})
        except:
            pass

    # Точки выбранной работы
    task_change_data = []
    if selected_task:
        task_records = db.session.query(ServiceHistory).join(
            ServiceHistoryTask
        ).filter(
            ServiceHistoryTask.service_task_id == selected_task_id,
            ServiceHistory.car_id == selected_car_id,
            ServiceHistory.mileage.isnot(None)
        ).order_by(ServiceHistory.service_date).all()

        for r in task_records:
            try:
                date_str = r.service_date if isinstance(r.service_date, str) else r.service_date.strftime('%Y-%m-%d')
                task_change_data.append({'x': date_str, 'y': r.mileage})
            except:
                pass

    return render_template('report_general.html',
                          car=car,
                          generation_date=generation_date,
                          tasks=tasks,
                          selected_task_id=selected_task_id,
                          selected_task=selected_task,
                          expenses_by_type=expenses_by_type,
                          expenses_total=expenses_total,
                          service_by_sto=service_by_sto,
                          service_total=service_total,
                          fuel_total=fuel_total,
                          parts_by_type=parts_by_type,
                          parts_total=parts_total,
                          grand_total=grand_total,
                          operation_period=operation_period,
                          ownership_days=ownership_days,
                          cost_per_day=cost_per_day,
                          last_mileage=last_mileage,
                          cost_per_km=cost_per_km,
                          mileage_data=mileage_data,
                          task_change_data=task_change_data)


if __name__ == "__main__":
    app.run(debug=True)
