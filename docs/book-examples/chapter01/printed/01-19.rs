// Definição de evento de domínio
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug)]
struct OrderCreatedEvent {
    order_id: u64,
    user_id: u64,
    total_amount: f64,
    timestamp: String,
}
