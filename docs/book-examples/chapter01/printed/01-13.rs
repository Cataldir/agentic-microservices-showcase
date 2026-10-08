use serde::{Deserialize, Serialize};
#[derive(Serialize)]
struct PaymentRequest { order_id: u64, amount: f64,
    user_id: u64 }
#[derive(Deserialize)]
struct PaymentResponse { payment_id: u64,
    status: String, transaction_id: String }
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let request = PaymentRequest {
        order_id: 12345, amount: 99.99, user_id: 456,
    };
    let response = reqwest::Client::new()
        .post("http://payment-service:8080/api/payments")
        .json(&request)
        .timeout(std::time::Duration::from_secs(5))
        .send().await?;
    if response.status().is_success() {
        let payment: PaymentResponse = response.json().await?;
        println!("Pagamento: {} - {}", payment.payment_id,
            payment.status);
    } else {
        eprintln!("Erro no pagamento: {}", response.status());
    }
    Ok(())
}
