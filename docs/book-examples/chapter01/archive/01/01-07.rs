// Orquestração do fluxo de negócio
fn main() {
    let user_service = users::UserService;
    let order_service = orders::OrderService;
    let payment_service = payments::PaymentService;

    let user = user_service.create_user("Alice".to_string(), "alice@example.com".to_string());
    let order = order_service.create_order(&user, 99.99);
    let payment = payment_service.process_payment(&order);

    println!("Payment status: {:?}", payment.status);
}
