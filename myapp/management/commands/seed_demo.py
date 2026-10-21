
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from myapp.models import Customer, Product, Order, OrderItem, SupportTicket


DEMO_PRODUCTS = [
    ("DEMO-P001", "陶瓷馬克杯", "450.00", 80),
    ("DEMO-P002", "保溫隨行杯", "850.00", 60),
    ("DEMO-P003", "棉質浴巾組", "690.00", 45),
    ("DEMO-P004", "桌上收納架", "1200.00", 35),
    ("DEMO-P005", "香氛擴香組", "790.00", 50),
    ("DEMO-P006", "LED 閱讀燈", "1490.00", 30),
    ("DEMO-P007", "無線滑鼠", "790.00", 75),
    ("DEMO-P008", "藍牙鍵盤", "1590.00", 40),
    ("DEMO-P009", "無線耳機", "3600.00", 25),
    ("DEMO-P010", "行動電源", "1290.00", 55),
    ("DEMO-P011", "USB-C 擴充座", "2490.00", 30),
    ("DEMO-P012", "智慧檯燈", "2990.00", 20),
    ("DEMO-P013", "空氣清淨機", "12800.00", 15),
    ("DEMO-P014", "智慧除濕機", "8900.00", 12),
    ("DEMO-P015", "掃地機器人", "11900.00", 10),
]


FIXED_ORDERS = {
    1: {
        "items": [("DEMO-P002", 1)],
        "status": "paid",
    },
    2: {
        "items": [("DEMO-P001", 2), ("DEMO-P002", 1)],
        "status": "paid",
    },
    3: {
        "items": [("DEMO-P003", 1), ("DEMO-P005", 1)],
        "status": "shipped",
    },
    16: {
        "items": [("DEMO-P009", 1)],
        "status": "delivered",
    },
    36: {
        "items": [("DEMO-P013", 1)],
        "status": "delivered",
    },
}


ITEM_TEMPLATES = {
    "low": {
        1: [("DEMO-P002", 1)],
        2: [("DEMO-P001", 2), ("DEMO-P002", 1)],
        3: [
            ("DEMO-P001", 1),
            ("DEMO-P003", 1),
            ("DEMO-P005", 1),
        ],
    },
    "medium": {
        1: [("DEMO-P009", 1)],
        2: [("DEMO-P011", 1), ("DEMO-P008", 1)],
        3: [
            ("DEMO-P002", 1),
            ("DEMO-P006", 1),
            ("DEMO-P008", 1),
        ],
    },
    "high": {
        1: [("DEMO-P013", 1)],
        2: [("DEMO-P014", 1), ("DEMO-P001", 1)],
        3: [
            ("DEMO-P015", 1),
            ("DEMO-P003", 1),
            ("DEMO-P005", 1),
        ],
    },
}


ITEM_QUOTAS = {
    "low": {1: 12, 2: 12, 3: 6},
    "medium": {1: 5, 2: 8, 3: 5},
    "high": {1: 3, 2: 5, 3: 4},
}


STATUS_QUOTAS = {
    "pending": 8,
    "paid": 12,
    "shipped": 15,
    "delivered": 20,
    "cancelled": 5,
}


def get_demo_impact(number):
    if number <= 15 or 17 <= number <= 31:
        return "low"

    if number == 16 or 32 <= number <= 35 or 37 <= number <= 49:
        return "medium"

    return "high"


def get_demo_customer_number(number):
    if number <= 15:
        return number

    if number <= 25:
        return number

    if number <= 35:
        return number - 10

    return 26 + (number - 36) % 5


def build_demo_orders():
    item_remaining = {
        level: counts.copy()
        for level, counts in ITEM_QUOTAS.items()
    }

    status_remaining = STATUS_QUOTAS.copy()

    for number, spec in FIXED_ORDERS.items():
        level = get_demo_impact(number)

        item_remaining[level][len(spec["items"])] -= 1
        status_remaining[spec["status"]] -= 1

    orders = []

    for number in range(1, 61):
        level = get_demo_impact(number)

        if number in FIXED_ORDERS:
            spec = FIXED_ORDERS[number]
            items = list(spec["items"])
            status = spec["status"]

        else:
            item_count = next(
                count
                for count in (1, 2, 3)
                if item_remaining[level][count] > 0
            )

            item_remaining[level][item_count] -= 1
            items = list(ITEM_TEMPLATES[level][item_count])

            status = next(
                name
                for name, remaining in status_remaining.items()
                if remaining > 0
            )

            status_remaining[status] -= 1

        orders.append({
            "order_number": f"DEMO-O{number:03d}",
            "customer_number": get_demo_customer_number(number),
            "status": status,
            "items": items,
        })

    return orders


DEMO_ORDERS = build_demo_orders()


DEMO_TICKETS_FIXED = [
    {
        "demo_id": "DEMO-T001",
        "order_number": "DEMO-O001",
        "category": "delivery",
        "requested_action": "info",
        "waiting_hours": 2,
        "message": (
            "我想確認保溫隨行杯的出貨進度，"
            "目前還沒收到物流通知，謝謝。"
        ),
    },
    {
        "demo_id": "DEMO-T002",
        "order_number": "DEMO-O016",
        "category": "damaged",
        "requested_action": "refund",
        "waiting_hours": 30,
        "message": (
            "收到無線耳機後，發現右耳無法使用，"
            "包裝盒也有撞擊痕跡，希望客服協助退款。"
        ),
    },
    {
        "demo_id": "DEMO-T003",
        "order_number": "DEMO-O036",
        "category": "missing",
        "requested_action": "info",
        "waiting_hours": 80,
        "message": (
            "訂購的空氣清淨機已顯示送達，"
            "但拆箱後只有配件，沒有主機，"
            "希望能盡快協助調查。"
        ),
    },
]


DEMO_TICKET_QUOTAS = {
    "delivery": {
        "info": 7,
        "refund": 2,
        "compensation": 1,
        "other": 2,
    },
    "refund": {
        "info": 1,
        "refund": 9,
    },
    "damaged": {
        "info": 1,
        "refund": 3,
        "exchange": 4,
    },
    "missing": {
        "info": 1,
        "refund": 2,
        "compensation": 1,
    },
    "other": {
        "info": 6,
    },
}

DEMO_TICKET_MESSAGES = {
    ("delivery", "info"): [
        "想確認訂單目前的出貨進度，物流頁面一直沒有更新，謝謝。",
        "商品已經付款，但還沒有收到出貨通知，想知道預計何時寄出。",
        "物流顯示配送中，想確認大約什麼時候可以收到商品。",
    ],
    ("delivery", "refund"): [
        "訂單配送時間比原先預計晚很多，目前已不需要商品，希望協助退款。",
        "商品遲遲沒有送達，想取消這筆訂單並申請退款。",
    ],
    ("delivery", "compensation"): [
        "商品配送延誤影響原本的使用安排，希望了解是否有補償方案。",
    ],
    ("delivery", "other"): [
        "物流資訊與實際收貨情況不一致，希望客服協助調查。",
        "配送地址可能需要確認，請協助聯絡物流處理。",
    ],
    ("refund", "info"): [
        "想了解這筆訂單目前是否符合退款條件，以及需要準備哪些資料。",
    ],
    ("refund", "refund"): [
        "已提出退款申請，但目前還沒有收到處理通知，希望確認進度。",
        "訂單取消後尚未收到退款，想請客服協助確認。",
        "退款金額與原先付款金額似乎不同，希望協助核對。",
    ],
    ("damaged", "info"): [
        "收到商品後發現部分功能不正常，想了解保固及後續處理方式。",
    ],
    ("damaged", "refund"): [
        "商品收到時外殼已有損壞，而且無法正常使用，希望申請退款。",
        "開箱後發現商品有明顯瑕疵，想退回商品並辦理退款。",
    ],
    ("damaged", "exchange"): [
        "收到商品後發現外殼有裂痕，希望協助更換正常商品。",
        "商品使用時出現異常，想申請換貨，請告知處理流程。",
        "剛收到的商品無法正常啟動，希望安排更換新品。",
    ],
    ("missing", "info"): [
        "收到包裹後發現部分商品沒有放入，想先確認是否分批出貨。",
    ],
    ("missing", "refund"): [
        "訂單中的部分商品沒有收到，希望協助辦理缺少商品的退款。",
        "收到的商品數量與訂單不符，想針對缺少部分申請退款。",
    ],
    ("missing", "compensation"): [
        "包裹內少了一項商品，已影響使用安排，希望了解補償方式。",
    ],
    ("other", "info"): [
        "想了解商品的基本操作方式，說明書有些地方不太清楚。",
        "請問商品保固期限如何計算，需要保留哪些購買證明？",
        "想確認商品是否支援目前使用的設備。",
        "想了解商品日常清潔與保養的注意事項。",
        "請問這項商品是否有相關配件可以另外購買？",
        "想詢問商品的使用限制與安全注意事項。",
    ],
}

def build_demo_tickets():
    remaining = {
        category: actions.copy()
        for category, actions in DEMO_TICKET_QUOTAS.items()
    }

    tickets = [
        ticket.copy()
        for ticket in DEMO_TICKETS_FIXED
    ]

    used_orders = set()

    # 扣除核心 Ticket 已使用的配額
    for ticket in tickets:
        category = ticket["category"]
        action = ticket["requested_action"]

        remaining[category][action] -= 1
        used_orders.add(ticket["order_number"])

    if any(
        count < 0
        for actions in remaining.values()
        for count in actions.values()
    ):
        raise ValueError("Fixed Ticket exceeds quota")

    # 建立固定商品價格對照
    prices = {
        code: Decimal(price)
        for code, _, price, _ in DEMO_PRODUCTS
    }

    low_orders = []

    for order in DEMO_ORDERS:
        total = sum(
            prices[code] * quantity
            for code, quantity in order["items"]
        )

        if total < 3000:
            low_orders.append(order["order_number"])

    all_orders = [
        order["order_number"]
        for order in DEMO_ORDERS
    ]

    # 建立其餘 Category / Requested Action 組合
    combinations = []

    for category, actions in remaining.items():
        for action, count in actions.items():
            combinations.extend(
                [(category, action)] * count
            )

    # 優先將 info 案件分配給 Low Impact 訂單
    combinations.sort(
        key=lambda pair: pair[1] != "info"
    )

    # 產生剩餘 37 筆 Ticket 規格
    for number, (category, action) in enumerate(
        combinations,
        start=4,
    ):
        candidates = (
            low_orders
            if action == "info"
            else all_orders
        )

        order_number = next(
            (
                order
                for order in candidates
                if order not in used_orders
            ),
            None,
        )

        if order_number is None:
            raise ValueError(
                f"No available Order for DEMO-T{number:03d}"
            )

        used_orders.add(order_number)

        demo_id = f"DEMO-T{number:03d}"

        message_options = DEMO_TICKET_MESSAGES[(category, action)]

        message_index = (number - 4) % len(message_options)

        message = message_options[message_index]

        tickets.append({
            "demo_id": demo_id,
            "order_number": order_number,
            "category": category,
            "requested_action": action,
            "waiting_hours": 2,
            "message": message,
        })

    if len(tickets) != 40:
        raise ValueError("Invalid Demo Ticket count")

    if len(used_orders) != 40:
        raise ValueError("Duplicate Demo Ticket Order")

    return tickets


DEMO_TICKETS = build_demo_tickets()

# 成果發表保留的六筆未評估案件
DEMO_LIVE_TICKET_IDS = {
    "DEMO-T001",
    "DEMO-T002",
    "DEMO-T004",
    "DEMO-T025",
    "DEMO-T034",
    "DEMO-T040",
}

class Command(BaseCommand):
    help = "Initialize demo data for small_business_ai_ops"

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-tickets",
            action="store_true",
            help="Explicitly allow creating Demo SupportTickets",
        )

    def handle(self, *args, **options):
        product_specs = {
            code: (name, Decimal(price), stock)
            for code, name, price, stock in DEMO_PRODUCTS
        }

        with transaction.atomic():

            # 1. 檢查既有 Customer
            for i in range(1, 31):
                email = f"demo{i:03d}@example.com"
                name = f"Demo 客戶 {i:03d}"
                phone = f"0900{i:06d}"

                existing = Customer.objects.filter(
                    email=email
                ).first()

                if existing is not None and (
                    existing.name != name
                    or existing.phone != phone
                ):
                    raise CommandError(
                        f"Demo Customer conflict: {email}"
                    )

            # 2. 檢查既有 Product
            for code, (name, price, stock) in product_specs.items():
                existing = Product.objects.filter(
                    product_code=code
                ).first()

                if existing is not None and (
                    existing.name != name
                    or existing.price != price
                    or existing.stock != stock
                ):
                    raise CommandError(
                        f"Demo Product conflict: {code}"
                    )

            # 3. 檢查既有 Order / OrderItem
            seen_orders = set()

            for order_data in DEMO_ORDERS:
                number = order_data["order_number"]
                customer_number = order_data["customer_number"]
                status = order_data["status"]

                email = (
                    f"demo{customer_number:03d}@example.com"
                )

                address = (
                    f"桃園市桃園區展示路{customer_number}號"
                )

                expected_items = []

                if number in seen_orders:
                    raise CommandError(
                        f"Duplicate Demo Order spec: {number}"
                    )

                seen_orders.add(number)

                if not 1 <= customer_number <= 30:
                    raise CommandError(
                        f"Invalid Demo Customer: {number}"
                    )

                if status not in dict(Order.STATUS_CHOICES):
                    raise CommandError(
                        f"Invalid Demo Order status: {number}"
                    )

                if not order_data["items"]:
                    raise CommandError(
                        f"Empty Demo Order items: {number}"
                    )

                for code, quantity in order_data["items"]:
                    if code not in product_specs or quantity <= 0:
                        raise CommandError(
                            f"Invalid Demo OrderItem: {number}"
                        )

                    expected_items.append(
                        (
                            code,
                            quantity,
                            product_specs[code][1],
                        )
                    )

                if len({
                    code
                    for code, _, _ in expected_items
                }) != len(expected_items):
                    raise CommandError(
                        f"Duplicate product in Demo Order: {number}"
                    )

                existing_order = Order.objects.filter(
                    order_number=number
                ).first()

                if existing_order is None:
                    continue

                if (
                    existing_order.customer.email != email
                    or existing_order.status != status
                    or existing_order.shipping_address != address
                ):
                    raise CommandError(
                        f"Demo Order conflict: {number}"
                    )

                existing_items = list(
                    OrderItem.objects.filter(
                        order=existing_order
                    ).select_related("product")
                )

                actual_items = sorted(
                    (
                        item.product.product_code,
                        item.quantity,
                        item.unit_price,
                    )
                    for item in existing_items
                )

                if actual_items != sorted(expected_items):
                    raise CommandError(
                        f"Demo OrderItem conflict: {number}"
                    )

            # 4. 只有明確啟用時才檢查 Ticket
            if options["with_tickets"]:
                self._check_demo_tickets()

            # 5. 建立尚未存在的 Customer
            customer_created = 0

            for i in range(1, 31):
                _, created = Customer.objects.get_or_create(
                    email=f"demo{i:03d}@example.com",
                    defaults={
                        "name": f"Demo 客戶 {i:03d}",
                        "phone": f"0900{i:06d}",
                    },
                )

                customer_created += int(created)

            # 6. 建立尚未存在的 Product
            product_created = 0

            for code, (name, price, stock) in product_specs.items():
                _, created = Product.objects.get_or_create(
                    product_code=code,
                    defaults={
                        "name": name,
                        "price": price,
                        "stock": stock,
                    },
                )

                product_created += int(created)

            # 7. 建立 Order 與 OrderItem
            order_created = 0
            item_created = 0

            for order_data in DEMO_ORDERS:
                number = order_data["order_number"]
                customer_number = order_data["customer_number"]

                customer = Customer.objects.get(
                    email=f"demo{customer_number:03d}@example.com"
                )

                order, created = Order.objects.get_or_create(
                    order_number=number,
                    defaults={
                        "customer": customer,
                        "status": order_data["status"],
                        "shipping_address": (
                            f"桃園市桃園區展示路{customer_number}號"
                        ),
                    },
                )

                if created:
                    order_created += 1

                    for code, quantity in order_data["items"]:
                        product = Product.objects.get(
                            product_code=code
                        )

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=quantity,
                            unit_price=product_specs[code][1],
                        )

                        item_created += 1

            # 8. 只有明確啟用才建立 SupportTicket
            ticket_created = 0

            if options["with_tickets"]:
                baseline = timezone.now()

                for ticket_data in DEMO_TICKETS:
                    marker = f"[{ticket_data['demo_id']}]"

                    message = (
                        f"{marker} {ticket_data['message']}"
                    )

                    if SupportTicket.objects.filter(
                        message__startswith=marker
                    ).exists():
                        continue

                    order = Order.objects.get(
                        order_number=ticket_data["order_number"]
                    )

                    ticket = SupportTicket.objects.create(
                        customer=order.customer,
                        order=order,
                        category=ticket_data["category"],
                        requested_action=ticket_data["requested_action"],
                        status="open",
                        message=message,
                    )

                    # 只調整本次新建立 Ticket 的時間
                    created_at = baseline - timedelta(
                        hours=ticket_data["waiting_hours"]
                    )

                    SupportTicket.objects.filter(
                        pk=ticket.pk
                    ).update(
                        created_at=created_at
                    )

                    ticket_created += 1

        # 初始化結果輸出
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo Customers: created={customer_created}, "
                f"skipped={30 - customer_created}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo Products: created={product_created}, "
                f"skipped={len(product_specs) - product_created}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo Orders: created={order_created}, "
                f"skipped={len(DEMO_ORDERS) - order_created}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo OrderItems: created={item_created}"
            )
        )

        if options["with_tickets"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo Tickets: created={ticket_created}, "
                    f"skipped={len(DEMO_TICKETS) - ticket_created}"
                )
            )

    def _check_demo_tickets(self):
        for ticket_data in DEMO_TICKETS:
            demo_id = ticket_data["demo_id"]
            marker = f"[{demo_id}]"

            expected_message = (
                f"{marker} {ticket_data['message']}"
            )

            matches = list(
                SupportTicket.objects.filter(
                    message__startswith=marker
                )
            )

            if len(matches) > 1:
                raise CommandError(
                    f"Duplicate Demo Ticket marker: {demo_id}"
                )

            if not matches:
                continue

            existing_ticket = matches[0]

            if (
                existing_ticket.order.order_number
                != ticket_data["order_number"]
                or existing_ticket.customer_id
                != existing_ticket.order.customer_id
                or existing_ticket.category
                != ticket_data["category"]
                or existing_ticket.requested_action
                != ticket_data["requested_action"]
                or existing_ticket.message
                != expected_message
            ):
                raise CommandError(
                    f"Demo Ticket conflict: {demo_id}"
                )
