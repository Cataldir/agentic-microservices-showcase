pub async fn execute<F, T, E>(&self, mut operation: F,
  waiter: &mut impl Waiter) -> Result<T, String>
where F: FnMut() -> Result<T, E>, E: std::fmt::Display
{
  let mut attempt = 0;
  let mut delay = self.initial_delay;
  loop {
    match operation() {
      Ok(value) => return Ok(value),
      Err(error) => {
        attempt += 1;
        if attempt >= self.max_retries {
          return Err(format!(
            "Falhou após {attempt} tentativas: {error}"
          ));
        }
        waiter.wait(delay).await;
        delay = std::cmp::min(
          std::time::Duration::from_secs_f64(
            delay.as_secs_f64() * self.multiplier),
          self.max_delay);
      }
    }
  }
}
