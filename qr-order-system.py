from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import uuid
import qrcode
import io
import base64
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)

# ========== CONFIG ==========
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///orders.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'change-this-secret-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)

db = SQLAlchemy(app)
jwt = JWTManager(app)

# ========== MODELS ==========
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    table_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'order_id': self.id,
            'table_number': self.table_number,
            'status': self.status,
            'total_amount': self.total_amount,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(36), db.ForeignKey('orders.id'), nullable=False)
    item_id = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'item_id': self.item_id,
            'name': self.name,
            'quantity': self.quantity,
            'price': self.price
        }

class Staff(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='staff')  # 'admin' or 'staff'

# ========== VALID STATUSES ==========
VALID_STATUSES = ['pending', 'preparing', 'ready', 'served', 'paid', 'cancelled']

# ========== AUTH ROUTES ==========
@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Staff login
    Body: { "username": "admin", "password": "1234" }
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400

    staff = Staff.query.filter_by(username=data['username']).first()
    if not staff or staff.password != data['password']:  # ใน production ควรใช้ bcrypt
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_access_token(identity={'username': staff.username, 'role': staff.role})
    return jsonify({'access_token': token, 'role': staff.role}), 200

# ========== QR CODE ==========
@app.route('/api/qr/<string:table_number>', methods=['GET'])
def generate_qr(table_number):
    """
    สร้าง QR Code สำหรับโต๊ะ
    คืนค่าเป็น base64 image PNG
    """
    base_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    order_url = f"{base_url}/order?table={table_number}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(order_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return jsonify({
        'table_number': table_number,
        'url': order_url,
        'qr_image': f"data:image/png;base64,{img_base64}"
    }), 200

# ========== ORDER ROUTES ==========
@app.route('/api/orders', methods=['POST'])
def create_order():
    """
    ลูกค้าสร้างออเดอร์ (ไม่ต้อง login)
    Body: {
        "table_number": "T1",
        "items": [{"item_id": "001", "name": "ข้าวผัด", "quantity": 1, "price": 80}],
        "notes": "ไม่เผ็ด"
    }
    """
    data = request.get_json()
    if not data or 'table_number' not in data or 'items' not in data:
        return jsonify({'error': 'Missing table_number or items'}), 400

    if not data['items']:
        return jsonify({'error': 'Order must have at least one item'}), 400

    total = sum(i['quantity'] * i['price'] for i in data['items'])

    order = Order(
        table_number=data['table_number'],
        notes=data.get('notes', ''),
        total_amount=total
    )
    db.session.add(order)
    db.session.flush()

    for i in data['items']:
        item = OrderItem(
            order_id=order.id,
            item_id=i['item_id'],
            name=i['name'],
            quantity=i['quantity'],
            price=i['price']
        )
        db.session.add(item)

    db.session.commit()
    return jsonify(order.to_dict()), 201

@app.route('/api/orders', methods=['GET'])
@jwt_required()
def get_all_orders():
    """ดูออเดอร์ทั้งหมด (Staff เท่านั้น) กรองด้วย ?status=pending"""
    status_filter = request.args.get('status')
    query = Order.query.order_by(Order.created_at.desc())
    if status_filter:
        query = query.filter_by(status=status_filter)
    return jsonify([o.to_dict() for o in query.all()]), 200

@app.route('/api/orders/<string:order_id>', methods=['GET'])
def get_order(order_id):
    """ดูออเดอร์ตาม ID"""
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    return jsonify(order.to_dict()), 200

@app.route('/api/orders/<string:order_id>/status', methods=['PUT'])
@jwt_required()
def update_status(order_id):
    """
    Staff อัปเดตสถานะ (ต้อง login)
    Body: { "status": "preparing" }
    """
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'Missing status'}), 400

    new_status = data['status'].lower()
    if new_status not in VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Use: {", ".join(VALID_STATUSES)}'}), 400

    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    order.status = new_status
    order.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(order.to_dict()), 200

@app.route('/api/orders/<string:order_id>', methods=['DELETE'])
@jwt_required()
def delete_order(order_id):
    """ลบออเดอร์ (Admin เท่านั้น)"""
    current = get_jwt_identity()
    if current.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403

    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    db.session.delete(order)
    db.session.commit()
    return jsonify({'message': 'Order deleted'}), 200

# ========== SUMMARY ==========
@app.route('/api/summary', methods=['GET'])
@jwt_required()
def summary():
    """สรุปยอดขายวันนี้"""
    today = datetime.utcnow().date()
    orders_today = Order.query.filter(
        db.func.date(Order.created_at) == today
    ).all()

    total_revenue = sum(o.total_amount for o in orders_today if o.status == 'paid')
    by_status = {}
    for o in orders_today:
        by_status[o.status] = by_status.get(o.status, 0) + 1

    return jsonify({
        'date': today.isoformat(),
        'total_orders': len(orders_today),
        'total_revenue': total_revenue,
        'by_status': by_status
    }), 200

# ========== INIT DB ==========
@app.route('/api/setup', methods=['POST'])
def setup():
    """สร้าง DB และ admin เริ่มต้น (ใช้ครั้งเดียวตอน deploy)"""
    db.create_all()
    if not Staff.query.filter_by(username='admin').first():
        admin = Staff(username='admin', password='admin1234', role='admin')
        db.session.add(admin)
        db.session.commit()
    return jsonify({'message': 'Setup complete. Change admin password immediately!'}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
