impl CircuitBreaker {
    fn on_success(&self) {
        let mut state = self.state.lock().unwrap();
        *state = CircuitState::Closed;
        *self.failure_count.lock().unwrap() = 0;
    }

    fn on_failure(&self) {
        let mut count = self.failure_count.lock().unwrap();
        *count += 1;

        if *count >= self.failure_threshold {
            *self.state.lock().unwrap() = CircuitState::Open;
            *self.last_failure_time.lock().unwrap() = Some(Instant::now());
        }
    }
}
