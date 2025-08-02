from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout,get_user_model,update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .models import User,Product,CartItem,Order,OrderItem,Review,WishlistItem
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required,user_passes_test
from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from .forms import EditProfileForm

from django.db.models import Q

def home(request):
    query = request.GET.get('q')
    category = request.GET.get('category')

    products = Product.objects.all()

    if category:
        products = products.filter(category__iexact=category)

    if query:
        products = products.filter(Q(name__icontains=query))

    return render(request, 'core/home.html', {
        'products': products,
        'selected_category': category,
        'query': query
    })

def register(request):
    if request.method == 'POST':
        first = request.POST['first_name']
        last = request.POST['last_name']
        email = request.POST['email']
        password = request.POST['password']

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('register')

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=first,
            last_name=last,
            password=password
        )
        user.save()
        messages.success(request, 'Account created successfully. Please log in.')
        return redirect('login')
    return render(request, 'core/register.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next') or 'home'
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid email or password')
            return redirect('login')

    next_url = request.GET.get('next', '')
    return render(request, 'core/login.html', {'next': next_url})
    
def logout_view(request):
    logout(request)
    return redirect('home')

User = get_user_model()

def register_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, 'Passwords do not match')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is  already registered")
            return redirect('register')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
        )
        user.phone = phone
        user.save()

        login(request,user)
        messages.success(request, "Account created successfully!")
        return redirect('home')

    return render(request, 'core/register.html')

@login_required(login_url='login')
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews = Review.objects.filter(product=product)

    if request.method == 'POST':
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment')

        Review.objects.create(
            user=request.user,
            product=product,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Review submitted.")
        return redirect('product_detail', product_id=product.id)

    return render(request, 'core/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'ratings': range(1, 6)
    })


@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    selected_size = request.POST.get('selected_size')

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': quantity},
        selected_size=selected_size
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    return redirect('home')  # or redirect('cart') once we build the cart page

@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render(request, 'core/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price
    })


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    return redirect('cart')

@login_required
def update_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        item.quantity = quantity
        item.save()
    return redirect('cart')

@login_required
def place_order(request):
    cart_items = CartItem.objects.filter(user=request.user)
    payment_method = request.POST.get('payment_method')  # Will be "COD" or "UPI"


    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

    out_of_stock_items = []
    for item in cart_items:
        if item.product.stock < item.quantity:
            out_of_stock_items.append(item.product.name)

    if out_of_stock_items:
        messages.error(request, f"Sorry, the following items are out of stock or not enough: {', '.join(out_of_stock_items)}")
        return redirect('cart')


    if request.method == 'POST':
        shipping_address = request.POST.get('shipping_address')
        payment_method = request.POST.get('payment_method')
        total_price = sum(item.product.price * item.quantity for item in cart_items)

        order = Order.objects.create(
            user=request.user,
            shipping_address=shipping_address,
            total_price=Decimal(total_price),
            payment_method=payment_method 
        )

        for item in cart_items:
            item.product.stock -= item.quantity
            item.product.save()

            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )

        cart_items.delete()
        messages.success(request, "Order placed successfully!")
        return redirect('order_success') 

    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render(request, 'core/place_order.html', {
        'cart_items': cart_items,
        'total_price': total_price
    })

#order success
def order_success(request):
    return render(request, 'core/order_success.html')

#order history
@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/order_history.html', {'orders': orders})

@staff_member_required
def admin_orders(request):
    orders = Order.objects.all().order_by('-created_at')
    return render(request, 'core/admin_orders.html', {'orders': orders})

@staff_member_required
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get('status')
    if new_status in dict(Order.STATUS_CHOICES):
        order.status = new_status
        order.save()
        messages.success(request, f"Order #{order.id} updated to {new_status}")
    return redirect('admin_orders')

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    WishlistItem.objects.get_or_create(user=request.user, product=product)
    return redirect('wishlist')

@login_required
def wishlist_view(request):
    wishlist_items = WishlistItem.objects.filter(user=request.user)
    return render(request, 'core/wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def remove_from_wishlist(request, product_id):
    item = get_object_or_404(WishlistItem, user=request.user, product_id=product_id)
    item.delete()
    return redirect('wishlist')


def admin_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')  # ✅ move to dashboard
        else:
            messages.error(request, "Invalid credentials or not an admin user")
            return render(request, 'core/admin_login.html')

    return render(request, 'core/admin_login.html')


def is_admin(user):
    return user.is_authenticated and user.is_superuser  # or however you mark admins

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='Pending').count()
    shipped_orders = Order.objects.filter(status='Shipped').count()
    delivered_orders = Order.objects.filter(status='Delivered').count()
    cancelled_orders = Order.objects.filter(status='Cancelled').count()
    total_products = Product.objects.count()

    context = {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'total_products': total_products,
    }
    return render(request, 'core/admin_dashboard.html', context)

@user_passes_test(lambda u: u.is_staff)
def admin_orders(request):
    orders = Order.objects.all().order_by('-created_at')
    return render(request, 'core/admin_orders.html', {'orders': orders})


@login_required
def add_product(request):
    if request.method == 'POST':
        name = request.POST['name']
        description = request.POST['description']
        price = request.POST['price']
        stock = request.POST['stock']
        sizes = request.POST.get('sizes')
        image = request.FILES.get('image')
        category = request.POST['category'] 

        Product.objects.create(
            name=name,
            description=description,
            price=price,
            stock=stock,
            sizes=sizes,
            image=image,
            category = category
        )
        return render(request, 'core/add_product.html', {'success': 'Product added successfully!'})
    
    return render(request, 'core/add_product.html')

@login_required
def admin_products(request):
    if not request.user.is_superuser:
        return redirect('home')

    products = Product.objects.all()
    return render(request, 'core/admin_products.html', {'products': products})

@login_required
def delete_product(request, product_id):
    if not request.user.is_superuser:
        return redirect('home')

    try:
        product = Product.objects.get(id=product_id)
        product.delete()
        messages.success(request, f'Product "{product.name}" deleted.')
    except Product.DoesNotExist:
        messages.error(request, 'Product not found.')

    return redirect('admin_products')


@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product.name = request.POST['name']
        product.description = request.POST['description']
        product.price = request.POST['price']
        product.stock = request.POST['stock']
        product.sizes = request.POST.get('sizes')
        product.category = request.POST.get('category')

        if 'image' in request.FILES:
            product.image = request.FILES['image']

        product.save()
        messages.success(request, "✅ Product updated successfully!")
        return redirect('admin_products')

    return render(request, 'core/edit_product.html', {'product': product})

@login_required
def profile_view(request):
    return render(request, 'core/profile.html', {'user': request.user})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            print("password changes updated")
            update_session_auth_hash(request, form.user)  # Keeps user logged in
            messages.success(request, "Password changed successfully.")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the error below.")
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'core/change_password.html', {'form': form})


@login_required
def edit_profile(request):
    user = request.user

    if request.method == 'POST':
        form = EditProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')  # assumes you have a 'profile' URL
    else:
        form = EditProfileForm(instance=user)

    return render(request, 'core/edit_profile.html', {'form': form})





