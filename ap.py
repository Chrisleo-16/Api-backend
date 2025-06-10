from flask import *
from flask_cors import CORS
from flask_jwt_extended import *
from werkzeug.security import *
from pymongo import MongoClient
from bson import ObjectId
from datetime import *
import os
from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv
import re

# Import admin routes
# from admin_routes import admin_bp

load_dotenv()

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS= {'png','jpg','jpeg','gif','jfif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['JWT_SECRET_KEY'] = "LonvqDT63A0a8nKUMmc7x4UTdfr5Z08iDjRz68UAOxQ"
app.config['SECRET_KEY'] = "LonvqDT63A0a8nKUMmc7x4UTdfr5Z08iDjRz68UAOxQ"
app.config['JWT_ACCESS_TOKEN_EXPIRES']= timedelta(hours=24)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Initialize extensions
jwt = JWTManager(app)
CORS(app)

# This line of code confirms if the types of allowed file 
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS
# Register admin blueprint
# app.register_blueprint(admin_bp)

# MongoDB connection
MONGO_URI= os.getenv('MONGODB_URI')
client = MongoClient(MONGO_URI)
db = client['sweetdelightsdb']

# Collections
users_collection = db['users']
products_collection = db['products']
categories_collection = db['categories']
orders_collection = db['orders']
admin_users_collection = db['admin_users']
def init_database():
    """Initialize database with sample data"""
    print("🔄 Initializing database...")
    admin_password = generate_password_hash("{cooki$}267}")
    admin_users_collection.insert_one({
        'username': '$Uv#ndo',
        'password': admin_password,
        'email': 'admin@sweetdelights.com',
        'role': 'admin',
        'created_at': datetime.now()
    })

# Helper function to convert ObjectId to string
def convert_objectids(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, list):
        return [convert_objectids(v) for v in obj]
    elif isinstance(obj, dict):
        return{k: convert_objectids(v) for k, v in obj.items()}
    else:
        return obj


# Authentication Routes
@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        
        # Validation
        required_fields = ['firstName', 'lastName', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        email = data['email'].lower()
        
        # Check if user already exists
        if users_collection.find_one({'email': email}):
            return jsonify({'error': 'User already exists'}), 400
        
        # Validate email format
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Create user
        user_data = {
            'firstName': data['firstName'],
            'lastName': data['lastName'],
            'email': email,
            'password': generate_password_hash(data['password']),
            'createdAt': datetime.utcnow(),
            'isActive': True,
            'addresses': [],
            'favorites': []
        }
        
        result = users_collection.insert_one(user_data)
        
        # Create access token
        access_token = create_access_token(identity=str(result.inserted_id))
        
        return jsonify({
            'message': 'User created successfully',
            'access_token': access_token,
            'user': {
                'id': str(result.inserted_id),
                'firstName': data['firstName'],
                'lastName': data['lastName'],
                'email': email
            }
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
        
        email = data['email'].lower()
        user = users_collection.find_one({'email': email})
        
        if not user or not check_password_hash(user['password'], data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.get('isActive', True):
            return jsonify({'error': 'Account is deactivated'}), 401
        
        access_token = create_access_token(identity=str(user['_id']))
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'user': {
                'id': str(user['_id']),
                'firstName': user['firstName'],
                'lastName': user['lastName'],
                'email': user['email']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        user_id = get_jwt_identity()
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = convert_objectids(user)
        user_data.pop('password', None)  # Remove password from response
        
        return jsonify({'user': user_data}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Product Routes
@app.route('/api/add_products', methods=['POST'])
def add_products():
    try:
        name = request.form.get('name')
        price =request.form.get('price')
        category_name = request.form.get('category_name')
        description = request.form.get('description')
        image = request.files.get('image')

        if not all ([name, price, category_name, description]):
            return jsonify({'error':'There some missing fields required to e filled'})
        
        image_filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = filename
        else:
            return jsonify({'error':'Invalid or missing image file'})

        category = categories_collection.find_one({'name':category_name})
        if not category:
            category_result = categories_collection.insert_one({
                'name': category_name,
                'createdAt':datetime.now(),
                'isActive': True
            })
            category_id = (category_result.inserted_id)
        else:
            category_id = (category['_id'])
        
        
        new_product = {
            'name' : name,
            'price': float(price),
            'category_id': category_id,
            'category_name':category_name,
            'description': description,
            'image': image_filename,
            'isActive': True,
            'createdAt': datetime.now()
        }

        result = products_collection.insert_one(new_product)

        return jsonify({
            'messaage':'Product addedd successfully',
            'product_id': str(result.inserted_id),
            'image_url' :f"/uploads/{image_filename}"
        })
    
    except Exception as e :
        return jsonify({'error': str(e)})








@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        category = request.args.get('category')
        sort_by = request.args.get('sort', 'name')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '')
        
        # Build query
        query = {'isActive': True}
        if category:
            query['category'] = category
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'description': {'$regex': search, '$options': 'i'}}
            ]
        
        # Sort options
        sort_options = {
            'name': [('name', 1)],
            'price-low': [('price', 1)],
            'price-high': [('price', -1)],
            'rating': [('rating', -1)],
            'newest': [('createdAt', -1)]
        }
        
        sort_criteria = sort_options.get(sort_by, [('name', 1)])
        
        # Execute query with pagination
        skip = (page - 1) * limit
        cursor = (products_collection.find(query).sort(sort_criteria).skip(skip).limit(limit))
        docs = list(cursor)
        total = products_collection.count_documents(query)

        safe_docs = convert_objectids(docs)
        
        return jsonify({
            'products': safe_docs,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    try:
        product = products_collection.find_one({'_id': ObjectId(product_id), 'isActive': True})
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        return jsonify({'product': convert_objectids(product)}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        categories = list(categories_collection.find({'isActive': True}).sort('name', 1))
        enriched_categories = []
        for cat in categories:
            cat_id = cat['_id']
            products = list(products_collection.find({
                'category_id':cat_id,
                'isActive': True
            }))
            products = [convert_objectids(p) for p in products]
            cat['products'] = products
            enriched_categories.append(convert_objectids(cat))
        return jsonify({'categories': enriched_categories}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Authentication routes
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        print(f"🔐 Login attempt for username: {username}")
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Find admin user
        admin = admin_users_collection.find_one({'username': username})
        
        if not admin:
            print(f"❌ Admin user not found: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check password
        if not check_password_hash(admin['password'], password):
            print(f"❌ Invalid password for user: {username}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Create session
        session['admin_id'] = str(admin['_id'])
        session['admin_username'] = admin['username']
        
        print(f"✅ Admin login successful: {username}")
        
        return jsonify({
            'message': 'Login successful',
            'admin': {
                'id': str(admin['_id']),
                'username': admin['username'],
                'email': admin['email']
            }
        })
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({'message': 'Logout successful'})

@app.route('/api/admin/me', methods=['GET'])
def get_admin_profile():
    if 'admin_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        admin = admin_users_collection.find_one({'_id': ObjectId(session['admin_id'])})
        if not admin:
            return jsonify({'error': 'Admin not found'}), 404
        
        return jsonify({
            'admin': convert_objectids(admin)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/analytics', methods=['GET'])
def get_analytics():
    if 'admin_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Calculate analytics
        total_products = products_collection.count_documents({})
        total_orders = orders_collection.count_documents({})
        total_customers = users_collection.count_documents({})
        
        # Revenue calculation
        pipeline = [
            {'$group': {'_id': None, 'total_revenue': {'$sum': '$total'}}}
        ]
        revenue_result = list(orders_collection.aggregate(pipeline))
        total_revenue = revenue_result[0]['total_revenue'] if revenue_result else 0
        
        # Recent orders
        recent_orders = list(orders_collection.find().sort('created_at', -1).limit(5))
        
        # Low stock products
        low_stock_products = list(products_collection.find({'stock': {'$lt': 10}}))
        
        return jsonify({
            'analytics': {
                'total_products': total_products,
                'total_orders': total_orders,
                'total_customers': total_customers,
                'total_revenue': total_revenue,
                'recent_orders': convert_objectids(recent_orders),
                'low_stock_products': convert_objectids(low_stock_products)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
app.run(debug=True)


# # Cart Routes
# @app.route('/api/cart', methods=['GET'])
# @jwt_required()
# def get_cart():
#     try:
#         user_id = get_jwt_identity()
#         cart = cart_collection.find_one({'userId': user_id})
        
#         if not cart:
#             return jsonify({'cart': {'items': [], 'total': 0}}), 200
        
#         # Populate product details
#         for item in cart['items']:
#             product = products_collection.find_one({'_id': ObjectId(item['productId'])})
#             if product:
#                 item['product'] = convert_objectids(product)
        
#         return jsonify({'cart': convert_objectids(cart)}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/cart/add', methods=['POST'])
# @jwt_required()
# def add_to_cart():
#     try:
#         user_id = get_jwt_identity()
#         data = request.get_json()
        
#         product_id = data.get('productId')
#         quantity = data.get('quantity', 1)
        
#         if not product_id:
#             return jsonify({'error': 'Product ID is required'}), 400
        
#         # Verify product exists
#         product = products_collection.find_one({'_id': ObjectId(product_id), 'isActive': True})
#         if not product:
#             return jsonify({'error': 'Product not found'}), 404
        
#         # Get or create cart
#         cart = cart_collection.find_one({'userId': user_id})
#         if not cart:
#             cart = {
#                 'userId': user_id,
#                 'items': [],
#                 'createdAt': datetime.utcnow(),
#                 'updatedAt': datetime.utcnow()
#             }
        
#         # Check if item already in cart
#         existing_item = next((item for item in cart['items'] if item['productId'] == product_id), None)
        
#         if existing_item:
#             existing_item['quantity'] += quantity
#         else:
#             cart['items'].append({
#                 'productId': product_id,
#                 'quantity': quantity,
#                 'price': product['price'],
#                 'addedAt': datetime.utcnow()
#             })
        
#         cart['updatedAt'] = datetime.utcnow()
        
#         # Update or insert cart
#         if '_id' in cart:
#             cart_collection.update_one({'_id': cart['_id']}, {'$set': cart})
#         else:
#             cart_collection.insert_one(cart)
        
#         return jsonify({'message': 'Item added to cart successfully'}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/cart/update', methods=['PUT'])
# @jwt_required()
# def update_cart_item():
#     try:
#         user_id = get_jwt_identity()
#         data = request.get_json()
        
#         product_id = data.get('productId')
#         quantity = data.get('quantity')
        
#         if not product_id or quantity is None:
#             return jsonify({'error': 'Product ID and quantity are required'}), 400
        
#         cart = cart_collection.find_one({'userId': user_id})
#         if not cart:
#             return jsonify({'error': 'Cart not found'}), 404
        
#         # Update item quantity
#         for item in cart['items']:
#             if item['productId'] == product_id:
#                 if quantity <= 0:
#                     cart['items'].remove(item)
#                 else:
#                     item['quantity'] = quantity
#                 break
#         else:
#             return jsonify({'error': 'Item not found in cart'}), 404
        
#         cart['updatedAt'] = datetime.utcnow()
#         cart_collection.update_one({'_id': cart['_id']}, {'$set': cart})
        
#         return jsonify({'message': 'Cart updated successfully'}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/cart/remove', methods=['DELETE'])
# @jwt_required()
# def remove_from_cart():
#     try:
#         user_id = get_jwt_identity()
#         product_id = request.args.get('productId')
        
#         if not product_id:
#             return jsonify({'error': 'Product ID is required'}), 400
        
#         cart = cart_collection.find_one({'userId': user_id})
#         if not cart:
#             return jsonify({'error': 'Cart not found'}), 404
        
#         # Remove item from cart
#         cart['items'] = [item for item in cart['items'] if item['productId'] != product_id]
#         cart['updatedAt'] = datetime.utcnow()
        
#         cart_collection.update_one({'_id': cart['_id']}, {'$set': cart})
        
#         return jsonify({'message': 'Item removed from cart successfully'}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# # Promo Code Routes
# @app.route('/api/promo-codes/validate', methods=['POST'])
# def validate_promo_code():
#     try:
#         data = request.get_json()
#         code = data.get('code', '').upper()
#         order_total = data.get('orderTotal', 0)
        
#         if not code:
#             return jsonify({'error': 'Promo code is required'}), 400
        
#         promo = promo_codes_collection.find_one({
#             'code': code,
#             'isActive': True,
#             'expiresAt': {'$gt': datetime.utcnow()}
#         })
        
#         if not promo:
#             return jsonify({'error': 'Invalid or expired promo code'}), 400
        
#         # Check minimum order requirement
#         if promo.get('minOrder', 0) > order_total:
#             return jsonify({
#                 'error': f'Minimum order of ${promo["minOrder"]:.2f} required for this promo code'
#             }), 400
        
#         # Calculate discount
#         if promo['type'] == 'percentage':
#             discount = (order_total * promo['value']) / 100
#             if promo.get('maxDiscount'):
#                 discount = min(discount, promo['maxDiscount'])
#         else:  # fixed amount
#             discount = min(promo['value'], order_total)
        
#         return jsonify({
#             'valid': True,
#             'promo': convert_objectids(promo),
#             'discount': discount
#         }), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# # Order Routes
# @app.route('/api/orders', methods=['POST'])
# @jwt_required()
# def create_order():
#     try:
#         user_id = get_jwt_identity()
#         data = request.get_json()
        
#         # Validate required fields
#         required_fields = ['items', 'shippingAddress', 'paymentMethod']
#         for field in required_fields:
#             if not data.get(field):
#                 return jsonify({'error': f'{field} is required'}), 400
        
#         # Calculate totals
#         subtotal = 0
#         order_items = []
        
#         for item in data['items']:
#             product = products_collection.find_one({'_id': ObjectId(item['productId'])})
#             if not product:
#                 return jsonify({'error': f'Product {item["productId"]} not found'}), 404
            
#             item_total = product['price'] * item['quantity']
#             subtotal += item_total
            
#             order_items.append({
#                 'productId': item['productId'],
#                 'name': product['name'],
#                 'price': product['price'],
#                 'quantity': item['quantity'],
#                 'total': item_total
#             })
        
#         # Apply promo code if provided
#         discount = 0
#         promo_code = None
#         if data.get('promoCode'):
#             promo = promo_codes_collection.find_one({
#                 'code': data['promoCode'].upper(),
#                 'isActive': True,
#                 'expiresAt': {'$gt': datetime.utcnow()}
#             })
            
#             if promo and (not promo.get('minOrder') or subtotal >= promo['minOrder']):
#                 promo_code = promo['code']
#                 if promo['type'] == 'percentage':
#                     discount = (subtotal * promo['value']) / 100
#                     if promo.get('maxDiscount'):
#                         discount = min(discount, promo['maxDiscount'])
#                 else:
#                     discount = min(promo['value'], subtotal)
        
#         # Calculate final totals
#         discounted_subtotal = subtotal - discount
#         shipping = 5.99 if subtotal < 50 else 0
#         tax = discounted_subtotal * 0.08
#         total = discounted_subtotal + shipping + tax
        
#         # Generate order number
#         order_number = f"SW{int(datetime.utcnow().timestamp())}"
        
#         # Create order
#         order_data = {
#             'orderNumber': order_number,
#             'userId': user_id,
#             'items': order_items,
#             'subtotal': subtotal,
#             'discount': discount,
#             'promoCode': promo_code,
#             'shipping': shipping,
#             'tax': tax,
#             'total': total,
#             'shippingAddress': data['shippingAddress'],
#             'paymentMethod': data['paymentMethod'],
#             'status': 'processing',
#             'createdAt': datetime.utcnow(),
#             'estimatedDelivery': datetime.utcnow() + timedelta(days=4)
#         }
        
#         result = orders_collection.insert_one(order_data)
        
#         # Clear user's cart
#         cart_collection.delete_one({'userId': user_id})
        
#         return jsonify({
#             'message': 'Order created successfully',
#             'orderId': str(result.inserted_id),
#             'orderNumber': order_number,
#             'total': total
#         }), 201
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/orders', methods=['GET'])
# @jwt_required()
# def get_user_orders():
#     try:
#         user_id = get_jwt_identity()
#         page = int(request.args.get('page', 1))
#         limit = int(request.args.get('limit', 10))
        
#         skip = (page - 1) * limit
#         orders = list(orders_collection.find({'userId': user_id})
#                      .sort('createdAt', -1)
#                      .skip(skip)
#                      .limit(limit))
        
#         total = orders_collection.count_documents({'userId': user_id})
        
#         return jsonify({
#             'orders': convert_objectidss(orders),
#             'pagination': {
#                 'page': page,
#                 'limit': limit,
#                 'total': total,
#                 'pages': (total + limit - 1) // limit
#             }
#         }), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/orders/<order_id>', methods=['GET'])
# @jwt_required()
# def get_order(order_id):
#     try:
#         user_id = get_jwt_identity()
#         order = orders_collection.find_one({
#             '_id': ObjectId(order_id),
#             'userId': user_id
#         })
        
#         if not order:
#             return jsonify({'error': 'Order not found'}), 404
        
#         return jsonify({'order': convert_objectids(order)}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# # Favorites Routes
# @app.route('/api/favorites', methods=['GET'])
# @jwt_required()
# def get_favorites():
#     try:
#         user_id = get_jwt_identity()
#         user = users_collection.find_one({'_id': ObjectId(user_id)})
        
#         if not user:
#             return jsonify({'error': 'User not found'}), 404
        
#         favorite_ids = user.get('favorites', [])
#         favorites = []
        
#         for product_id in favorite_ids:
#             product = products_collection.find_one({'_id': ObjectId(product_id)})
#             if product:
#                 favorites.append(convert_objectids(product))
        
#         return jsonify({'favorites': favorites}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/favorites/add', methods=['POST'])
# @jwt_required()
# def add_to_favorites():
#     try:
#         user_id = get_jwt_identity()
#         data = request.get_json()
#         product_id = data.get('productId')
        
#         if not product_id:
#             return jsonify({'error': 'Product ID is required'}), 400
        
#         # Verify product exists
#         product = products_collection.find_one({'_id': ObjectId(product_id)})
#         if not product:
#             return jsonify({'error': 'Product not found'}), 404
        
#         # Add to favorites
#         users_collection.update_one(
#             {'_id': ObjectId(user_id)},
#             {'$addToSet': {'favorites': product_id}}
#         )
        
#         return jsonify({'message': 'Added to favorites successfully'}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @app.route('/api/favorites/remove', methods=['DELETE'])
# @jwt_required()
# def remove_from_favorites():
#     try:
#         user_id = get_jwt_identity()
#         product_id = request.args.get('productId')
        
#         if not product_id:
#             return jsonify({'error': 'Product ID is required'}), 400
        
#         # Remove from favorites
#         users_collection.update_one(
#             {'_id': ObjectId(user_id)},
#             {'$pull': {'favorites': product_id}}
#         )
        
#         return jsonify({'message': 'Removed from favorites successfully'}), 200
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
