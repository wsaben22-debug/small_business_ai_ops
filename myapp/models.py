from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

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

    REQUESTED_ACTION_CHOICES = [
        ('info', '資訊詢問'),
        ('exchange','換貨'),
        ('refund','退款'),
        ('compensation','補償'),
        ('other','其他'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete = models.SET_NULL, null = True)

    order = models.ForeignKey(Order, on_delete = models.PROTECT)

    category = models.CharField(max_length = 20, choices = CATEGORY_CHOICES, default = 'other')

    requested_action = models.CharField(
        max_length=20,
        choices = REQUESTED_ACTION_CHOICES,
        default='other'
    )

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

class TicketTriageDecision(models.Model):

    LEVEL_CHOICES = [
        ('low','Low'),
        ('medium','Medium'),
        ('high','High'),
    ]

    TRIGGER_TYPE_CHOICES = [
        ('created','Created'),
        ('updated','Updated'),
        ('manual','Manual'),
    ]

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.PROTECT,
        related_name='triage_decisions',
    )

    category_snapshot = models.CharField(max_length=20)

    requested_action_snapshot = models.CharField(max_length=20)

    order_status_snapshot = models.CharField(max_length=20)

    order_total_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    waiting_hours_snapshot = models.FloatField(
        validators=[MinValueValidator(0)],
    )

    severity_level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
    )

    severity_score = models.IntegerField()

    severity_reason = models.TextField()

    impact_level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
    )

    impact_score = models.IntegerField()

    impact_reason = models.TextField()

    urgency_level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
    )

    urgency_score = models.IntegerField()

    urgency_reason = models.TextField()

    priority_score = models.IntegerField()

    priority_level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
    )

    requires_human = models.BooleanField()

    human_reason = models.TextField()

    rule_version = models.CharField(max_length=20)

    trigger_type = models.CharField(
        max_length=20,
        choices=TRIGGER_TYPE_CHOICES,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        if not self._state.adding:

            raise ValidationError(
                "TicketTruageDecision is immutable and cannot be updated."
            )

        super().save(*args, **kwargs)

class TriageExecutionRecord(models.Model):

    EXECUTION_STATUS_CHOICES = [
        ("success", "Success"),
        ("skipped", "Skipped"),
        ("failed", "Failed"),
    ]

    decision = models.ForeignKey(
        TicketTriageDecision,
        on_delete=models.PROTECT,
        related_name="execution_records",
    )

    action_code = models.CharField(
        max_length=50,
    )

    execution_status = models.CharField(
        max_length=20,
        choices=EXECUTION_STATUS_CHOICES,
    )

    reason = models.TextField()

    ticket_status_before = models.CharField(
        max_length=20,
    )

    ticket_status_after = models.CharField(
        max_length=20,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )