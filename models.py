from app import db


class Car(db.Model):
    __tablename__ = 'cars'
    id = db.Column(db.Integer, primary_key=True)
    manufacturer = db.Column(db.String, nullable=True)
    name = db.Column(db.String, unique=True, nullable=False)
    year = db.Column(db.Integer, nullable=True)
    vin = db.Column(db.String, nullable=True)
    plate_number = db.Column(db.String, nullable=True)

    @property
    def display_name(self):
        values = [self.manufacturer, self.name, self.plate_number]
        return ' '.join(str(value) for value in values if value)

    def __repr__(self):
        return f"<Car {self.manufacturer} {self.name}>"


class Manufacturer(db.Model):
    __tablename__ = 'manufacturers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    country = db.Column(db.String, nullable=True)


class PartType(db.Model):
    __tablename__ = 'part_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)


class CarSystem(db.Model):
    __tablename__ = 'car_systems'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)


class Part(db.Model):
    __tablename__ = 'parts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    manufacturer_id = db.Column(db.Integer, db.ForeignKey('manufacturers.id'))
    type_id = db.Column(db.Integer, db.ForeignKey('part_types.id'))
    system_id = db.Column(db.Integer, db.ForeignKey('car_systems.id'))
    article = db.Column(db.String, nullable=True)
    original_article = db.Column(db.String, nullable=True)
    manufacturer = db.relationship('Manufacturer', foreign_keys=[manufacturer_id])

    @property
    def display_name(self):
        values = [self.article, self.name, self.manufacturer.name if self.manufacturer else None]
        return ' '.join(str(value) for value in values if value)


class ExpenseType(db.Model):
    __tablename__ = 'expense_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False)
    expense_type_id = db.Column(db.Integer, db.ForeignKey('expense_types.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.String, nullable=False)
    comment = db.Column(db.String, nullable=True)


class Fuel(db.Model):
    __tablename__ = 'fuel'
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'))
    liters = db.Column(db.Float, nullable=True)
    price = db.Column(db.Float, nullable=True)
    fuel_date = db.Column(db.String, nullable=True)


class PartPurchase(db.Model):
    __tablename__ = 'part_purchases'
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey('parts.id'), nullable=False)
    purchase_date = db.Column(db.String, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    service_history_id = db.Column(db.Integer, db.ForeignKey('service_history.id'))
    part = db.relationship('Part', foreign_keys=[part_id])
    service_history = db.relationship('ServiceHistory', foreign_keys=[service_history_id])


class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)


class ServiceTask(db.Model):
    __tablename__ = 'service_tasks'
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False)
    abbr = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    interval_km = db.Column(db.Integer, nullable=True)
    interval_months = db.Column(db.Integer, nullable=True)
    car = db.relationship('Car', foreign_keys=[car_id])


class ServiceHistory(db.Model):
    __tablename__ = 'service_history'
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False)
    service_date = db.Column(db.String, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    sto_id = db.Column(db.Integer, db.ForeignKey('services.id'))
    description = db.Column(db.String, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    service = db.relationship('Service', foreign_keys=[sto_id])

    @property
    def display_name(self):
        sto_name = self.service.name if self.service else '—'
        return f"{self.service_date} - {sto_name} - {self.mileage} км"


class ServiceHistoryTask(db.Model):
    __tablename__ = 'service_history_tasks'
    id = db.Column(db.Integer, primary_key=True)
    service_history_id = db.Column(db.Integer, db.ForeignKey('service_history.id'), nullable=False)
    service_task_id = db.Column(db.Integer, db.ForeignKey('service_tasks.id'), nullable=False)
    service_task = db.relationship('ServiceTask', foreign_keys=[service_task_id])


ServiceHistory.task_links = db.relationship(
    'ServiceHistoryTask',
    foreign_keys=[ServiceHistoryTask.service_history_id],
    cascade='all, delete-orphan',
    lazy='selectin')
