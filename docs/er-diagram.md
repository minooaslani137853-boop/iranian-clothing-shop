# نمودار رابطه‌ای پیشنهادی

این مدل در `app/models.py` پیاده‌سازی شده و با `flask --app app:create_app init-db` ساخته می‌شود. migration نسخه‌بندی‌شده هنوز وجود ندارد. قیود مبلغ کل نسبت به اقلام و داشتن حداقل یک قلم باید در سرویس checkout مرحله بعد اعمال شوند؛ مدل به تنهایی این قواعد بین چند ردیف را تضمین نمی‌کند.

```mermaid
erDiagram
    USER {
        integer id PK
        text email UK
        text password_hash
        text created_at
    }
    PRODUCT ||--o{ CART_ITEM : contains
    CART ||--o{ CART_ITEM : has
    CART ||--o{ CUSTOMER_ORDER : submits
    CUSTOMER_ORDER ||--|{ ORDER_ITEM : includes
    PRODUCT ||--o{ ORDER_ITEM : references
    PRODUCT {
        integer id PK
        text name
        text description
        text image_path
        integer price_toman
        integer stock
        text category
        text size
        text color
        boolean is_active
    }
    CART {
        text id PK
        text created_at
    }
    CART_ITEM {
        text cart_id PK,FK
        integer product_id PK,FK
        integer quantity
    }
    CUSTOMER_ORDER {
        integer id PK
        text cart_id FK
        text checkout_key UK
        text tracking_code UK
        text recipient_name
        text phone
        text address
        text status
        integer total_toman
        text created_at
    }
    ORDER_ITEM {
        integer id PK
        integer order_id FK
        integer product_id FK
        text product_name
        integer unit_price_toman
        integer quantity
    }
```

## قیود
- کلید مرکب `CART_ITEM(cart_id, product_id)` مانع ردیف تکراری شود.
- قیمت و موجودی نامنفی؛ تعداد صحیح مثبت؛ مبلغ کل برابر مجموع تعداد × قیمت snapshot اقلام و در سرویس تراکنشی کنترل شود.
- حذف سبد اقلام آن را cascade کند؛ سبد دارای سفارش حذف نشود. محصول دارای سابقه حذف نشود و به جای آن غیرفعال شود.
- نام و قیمت اقلام سفارش پس از تغییر محصول ثابت بمانند.
- `checkout_key` و `tracking_code` یکتا و غیرقابل حدس؛ زمان ISO 8601 در UTC.
- اطلاعات گیرنده در سفارش است؛ حساب کاربر در مرحله ۳ اضافه شده است ولی هنوز به سبد و سفارش متصل نیست. وضعیت اولیه `placed` فقط ثبت سفارش است، نه پرداخت بانکی.

مرحله ۳: جدول `user` با ایمیل یکتا و هش رمز و ستون‌های دسته، سایز و رنگ محصول با مقدار پیش‌فرض خالی اضافه شدند. دستور `upgrade-db` داده مرحله ۲ را حفظ می‌کند.
