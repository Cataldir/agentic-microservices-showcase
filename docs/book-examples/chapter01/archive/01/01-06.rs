// Módulo de Pagamentos - Processamento financeiro isolado
mod payments {
    use super::orders::Order;

    pub enum PaymentStatus { Pending, Completed, Failed }

    pub struct Payment {
        pub id: u64,
        pub order_id: u64,
        pub status: PaymentStatus,
    }

    pub struct PaymentService;

    impl PaymentService {
        pub fn process_payment(&self, order: &Order) -> Payment {
            Payment { id: 1, order_id: order.id, status: PaymentStatus::Completed }
        }
    }
}
