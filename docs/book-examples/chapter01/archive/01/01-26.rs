// Implementação de Retry com Exponential Backoff em Rust
use std::time::Duration;
use tokio::time::sleep;

struct RetryPolicy {
    max_retries: u32,
    initial_delay: Duration,
    max_delay: Duration,
    multiplier: f64,
}

impl RetryPolicy {
    fn new() -> Self {
        RetryPolicy {
            max_retries: 5,
            initial_delay: Duration::from_millis(100),
            max_delay: Duration::from_secs(30),
            multiplier: 2.0,
        }
    }

    async fn execute_with_retry<F, T, E>(
        &self,
        mut operation: F,
    ) -> Result<T, String>
    where
        F: FnMut() -> Result<T, E>,
        E: std::fmt::Display,
    {
        let mut attempt = 0;
        let mut delay = self.initial_delay;

        loop {
            match operation() {
                Ok(result) => {
                    if attempt > 0 {
                        println!("Operação bem-sucedida após {} tentativas", attempt + 1);
                    }
                    return Ok(result);
                }
                Err(e) => {
                    attempt += 1;

                    if attempt >= self.max_retries {
                        return Err(format!(
                            "Operação falhou após {} tentativas: {}",
                            attempt, e
                        ));
                    }

                    println!("Tentativa {} falhou: {}. Aguardando {:?}...",
                             attempt, e, delay);

                    sleep(delay).await;

                    // Exponential backoff
                    delay = std::cmp::min(
                        Duration::from_secs_f64(
                            delay.as_secs_f64() * self.multiplier
                        ),
                        self.max_delay,
                    );
                }
            }
        }
    }
}

// Uso do Retry Policy
#[tokio::main]
async fn main() {
    let retry_policy = RetryPolicy::new();

    let mut counter = 0;
    let result = retry_policy.execute_with_retry(|| {
        counter += 1;
        if counter < 3 {
            Err("Serviço temporariamente indisponível")
        } else {
            Ok("Dados do serviço")
        }
    }).await;

    match result {
        Ok(data) => println!("Sucesso: {}", data),
        Err(e) => println!("Erro: {}", e),
    }
}
