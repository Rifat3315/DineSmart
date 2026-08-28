from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('menu/', views.menu, name='menu'),

    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/decrease/<int:item_id>/', views.decrease_cart_item, name='decrease_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/checkout/', views.checkout, name='checkout'),
    path('payment/<int:order_id>/', views.payment_simulate, name='payment_simulate'),

    path('reservation/', views.reservation, name='reservation'),
path('reservation/book/', views.book_reservation, name='book_reservation'),
path(
    'reservation/<int:reservation_id>/cancel/',
    views.cancel_reservation,
    name='cancel_reservation'
),
path(
    'reservation/attendance/<str:token>/',
    views.reservation_attendance,
    name='reservation_attendance'
),
    

    path('orders/', views.order_tracking, name='order_tracking'),
    path(
    'orders/<int:order_id>/cancel/',
    views.cancel_order,
    name='cancel_order'
),
    path('reviews/submit/', views.submit_review, name='submit_review'),
    path('reviews/delete/<int:review_id>/', views.delete_review, name='delete_review'),
    path('chatbot/ask/', views.chatbot_ask, name='chatbot_ask'),

    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Forgot password flow (built-in Django views, our own templates/styling)
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='password_reset.html',
            email_template_name='password_reset_email.html',
            subject_template_name='password_reset_subject.txt',
            success_url='/password-reset/sent/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/sent/',
        auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='password_reset_confirm.html',
            success_url='/password-reset/complete/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
        name='password_reset_complete',
    ),

    path('staff/login/', views.staff_login, name='staff_login'),
    path('staff/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/order/<int:order_id>/<str:new_status>/', views.staff_update_order, name='staff_update_order'),
    path('staff/reservation/<int:reservation_id>/<str:new_status>/', views.staff_update_reservation, name='staff_update_reservation'),
    path('staff/menu/add/', views.admin_menu_form, name='admin_menu_add'),
    path('staff/menu/<int:item_id>/edit/', views.admin_menu_form, name='admin_menu_edit'),
    path('staff/menu/<int:item_id>/delete/', views.admin_menu_delete, name='admin_menu_delete'),
]
