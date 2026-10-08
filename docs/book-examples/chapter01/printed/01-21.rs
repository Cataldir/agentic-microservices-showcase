// Consumidores independentes reagindo ao mesmo evento
async fn payment_event_handler(event: OrderCreatedEvent) {
    println!("Processando pagamento para pedido: {}",
        event.order_id);
    process_payment(event.order_id,
        event.total_amount).await;
}

async fn inventory_event_handler(event: OrderCreatedEvent) {
    println!("Reservando estoque para pedido: {}",
        event.order_id);
    reserve_inventory(event.order_id).await;
}

async fn process_payment(order_id: u64, amount: f64) {
    println!("Pagamento de {} processado para pedido {}",
        amount, order_id);
}

async fn reserve_inventory(order_id: u64) {
    println!("Estoque reservado para pedido {}", order_id);
}
