// Publicação de eventos sem bloqueio
async fn publish_order_event(order_id: u64, user_id: u64, total: f64) {
    let event = OrderCreatedEvent {
        order_id, user_id, total_amount: total,
        timestamp: chrono::Utc::now().to_rfc3339(),
    };

    println!("Evento publicado: pedido {} criado", event.order_id);
    // Em produção: enviar para RabbitMQ, Kafka, etc.
}
