// Módulo de Usuários - Gestão de identidade isolada
mod users {
    pub struct User {
        pub id: u64,
        pub name: String,
        pub email: String,
    }

    pub struct UserService;

    impl UserService {
        pub fn create_user(&self, name: String, email: String) -> User {
            User { id: 1, name, email }
        }

        pub fn get_user(&self, id: u64) -> Option<User> {
            Some(User {
                id,
                name: "John Doe".to_string(),
                email: "john@example.com".to_string(),
            })
        }
    }
}
