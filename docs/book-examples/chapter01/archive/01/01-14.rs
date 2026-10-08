// Definição dos estados do Circuit Breaker
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Debug, Clone, PartialEq)]
enum CircuitState {
    Closed,      // Funcionamento normal
    Open,        // Circuito aberto - rejeita chamadas
    HalfOpen,    // Teste - permite chamadas limitadas
}
