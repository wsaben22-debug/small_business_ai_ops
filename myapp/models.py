from django.db import models
from django.core.validators import MinValueValidator

class Customer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=100)
    stock = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    product_code = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending','待處理'),
        ('paid','已付款'),
        ('shipped','已出貨'),
        ('delivered','已送達'),
        ('cancelled','已取消'),
    ]
    customer = models.ForeignKey(Customer, on_delete = models.PROTECT)
    shipping_address = models.CharField(max_length = 255)
    status = models.CharField(max_length = 20, choices = STATUS_CHOICES, default = 'pending')
    order_date = models.DateTimeField(auto_now_add = True)
    order_number = models.CharField(max_length = 20, unique = True)
    def __str__(self):
        return self.order_number

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete = models.CASCADE)
    product = models.ForeignKey(Product, on_delete = models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits = 10, decimal_places = 2, validators=[MinValueValidator(0)])
    def __str__(self):
        return f'{self.order.order_number} - {self.product.name}'

class SupportTicket(models.Model):
    CATEGORY_CHOICES = [
        ('delivery','配送問題'),
        ('damaged','商品損壞'),
        ('missing','商品缺失'),
        ('refund','退款問題'),
        ('other','其他問題'),
    ]
    customer = models.ForeignKey(Customer, on_delete = models.SET_NULL, null = True)
    order = models.ForeignKey(Order, on_delete = models.PROTECT)
    category = models.CharField(max_length = 20, choices = CATEGORY_CHOICES, default = 'other')
    message = models.TextField()
    STATUS_CHOICES = [
        ('open','待處理'),
        ('in_progress','處理中'),
        ('resolved','已解決'),
        ('closed','已關閉'),
    ]
    status = models.CharField(max_length = 20, choices = STATUS_CHOICES, default = 'open')
    created_at = models.DateTimeField(auto_now_add = True)
    def __str__(self):
        return f'{self.order.order_number} - {self.get_category_display()}'
