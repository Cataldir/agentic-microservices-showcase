impl CircuitBreaker {
    async fn call<F, T, E>(&self, f: F) -> Result<T, String>
    where
        F: FnOnce() -> Result<T, E>,
        E: std::fmt::Display,
    {
        let mut state = self.state.lock().unwrap();
        match *state {
            CircuitState::Open => {
                if let Some(last_failure) =
                    *self.last_failure_time.lock().unwrap()
                {
                    if last_failure.elapsed() > self.timeout
                    {
                        *state = CircuitState::HalfOpen;
                    } else {
                        return Err(
                            "Circuit breaker is OPEN"
                                .to_string());
                    }
                }
            }
            _ => {}
        }
        drop(state); // Libera lock antes da chamada
        match f() {
            Ok(result) => {
                self.on_success();
                Ok(result)
            }
            Err(e) => {
                self.on_failure();
                Err(format!("Call failed: {}", e))
            }
        }
    }
}
