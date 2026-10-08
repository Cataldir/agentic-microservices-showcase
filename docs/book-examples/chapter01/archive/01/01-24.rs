// Implementação do padrão Saga Orquestrado em Rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Order {
    id: u64,
    user_id: u64,
    items: Vec<String>,
    total: f64,
}

#[derive(Debug)]
enum SagaStep {
    CreateOrder,
    ReserveInventory,
    ProcessPayment,
    SendNotification,
}

struct SagaOrchestrator;

impl SagaOrchestrator {
    async fn execute_saga(&self, order: Order) -> Result<(), String> {
        let mut completed_steps = Vec::new();

        // Passo 1: Criar Pedido
        match self.create_order(&order).await {
            Ok(_) => {
                println!("✓ Pedido criado: {}", order.id);
                completed_steps.push(SagaStep::CreateOrder);
            }
            Err(e) => return self.compensate(completed_steps).await,
        }

        // Passo 2: Reservar Estoque
        match self.reserve_inventory(&order).await {
            Ok(_) => {
                println!("✓ Estoque reservado");
                completed_steps.push(SagaStep::ReserveInventory);
            }
            Err(e) => {
                println!("✗ Falha ao reservar estoque: {}", e);
                return self.compensate(completed_steps).await;
            }
        }

        // Passo 3: Processar Pagamento
        match self.process_payment(&order).await {
            Ok(_) => {
                println!("✓ Pagamento processado");
                completed_steps.push(SagaStep::ProcessPayment);
            }
            Err(e) => {
                println!("✗ Falha no pagamento: {}", e);
                return self.compensate(completed_steps).await;
            }
        }

        // Passo 4: Enviar Notificação
        match self.send_notification(&order).await {
            Ok(_) => {
                println!("✓ Notificação enviada");
                completed_steps.push(SagaStep::SendNotification);
            }
            Err(e) => {
                println!("✗ Falha ao enviar notificação: {}", e);
                return self.compensate(completed_steps).await;
            }
        }

        println!("✓ Saga completada com sucesso!");
        Ok(())
    }

    async fn compensate(&self, completed_steps: Vec<SagaStep>) -> Result<(), String> {
        println!("⚠ Iniciando compensação da saga...");

        // Compensa na ordem reversa
        for step in completed_steps.iter().rev() {
            match step {
                SagaStep::CreateOrder => {
                    println!("↶ Cancelando pedido");
                    self.cancel_order().await?;
                }
                SagaStep::ReserveInventory => {
                    println!("↶ Liberando estoque");
                    self.release_inventory().await?;
                }
                SagaStep::ProcessPayment => {
                    println!("↶ Estornando pagamento");
                    self.refund_payment().await?;
                }
                SagaStep::SendNotification => {
                    println!("↶ Notificação de cancelamento");
                    self.send_cancellation_notification().await?;
                }
            }
        }

        println!("✓ Compensação concluída");
        Err("Saga falhou e foi compensada".to_string())
    }

    // Implementações dos passos e compensações (simplificadas)
    async fn create_order(&self, order: &Order) -> Result<(), String> { Ok(()) }
    async fn reserve_inventory(&self, order: &Order) -> Result<(), String> {
        // Simula falha ocasional
        if rand::random::<f32>() < 0.3 {
            return Err("Estoque insuficiente".to_string());
        }
        Ok(())
    }
    async fn process_payment(&self, order: &Order) -> Result<(), String> { Ok(()) }
    async fn send_notification(&self, order: &Order) -> Result<(), String> { Ok(()) }

    async fn cancel_order(&self) -> Result<(), String> { Ok(()) }
    async fn release_inventory(&self) -> Result<(), String> { Ok(()) }
    async fn refund_payment(&self) -> Result<(), String> { Ok(()) }
    async fn send_cancellation_notification(&self) -> Result<(), String> { Ok(()) }
}
