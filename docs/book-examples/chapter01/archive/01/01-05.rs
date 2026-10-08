// Módulo de Pedidos - Dependência explícita do módulo de usuários
mod orders {
    use super::users::User;

    pub struct Order {
        pub id: u64,
        pub user_id: u64,
        pub total: f64,
    }

    pub struct OrderService;

    impl OrderService {
        pub fn create_order(&self, user: &User, total: f64) -> Order {
            Order { id: 1, user_id: user.id, total }
        }
    }
}
