    pub async fn execute_saga(&mut self, order: Order)
        -> Result<(), String>
    {
        let mut completed = Vec::new();
        for step in [CreateOrder, ReserveInventory,
            ProcessPayment, SendNotification]
        {
            if self.execute_step(step, &order).await.is_err() {
                return self.compensate(completed).await;
            }
            completed.push(step);
        }
        Ok(())
    }
    async fn compensate(&mut self, completed: Vec<SagaStep>)
        -> Result<(), String>
    {
        for step in completed.iter().rev() {
            self.undo_step(*step).await?;
        }
        Err("Saga falhou e foi compensada".to_string())
    }
