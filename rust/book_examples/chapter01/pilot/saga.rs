#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum SagaStep {CreateOrder,ReserveInventory,ProcessPayment,SendNotification}
use SagaStep::*;
pub struct Order {
 pub id:u64,pub user_id:u64,pub items:Vec<String>,pub total:f64,
}
#[derive(Default)]
pub struct SagaOrchestrator {
 pub fail_at:Option<SagaStep>,pub fail_undo:Option<SagaStep>,
 pub trace:Vec<(bool,SagaStep)>,
}
impl SagaOrchestrator {
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

 async fn execute_step(&mut self,step:SagaStep,_order:&Order)->Result<(),String> {
  self.trace.push((true,step));
  if self.fail_at==Some(step){Err("Falha controlada".into())}else{Ok(())}
 }
 async fn undo_step(&mut self,step:SagaStep)->Result<(),String> {
  self.trace.push((false,step));
  if self.fail_undo==Some(step){Err("Compensação falhou".into())}else{Ok(())}
 }
}
#[cfg(test)]
mod tests {
 use super::*;use crate::support::run;
 fn order()->Order{Order{id:12345,user_id:456,items:vec!["item".into()],total:99.99}}
 #[test] fn success_runs_all_steps(){
  let mut s=SagaOrchestrator::default();
  assert_eq!(run(s.execute_saga(order())),Ok(()));
  assert_eq!(s.trace,vec![(true,CreateOrder),(true,ReserveInventory),
   (true,ProcessPayment),(true,SendNotification)]);
 }
 #[test] fn each_failure_compensates_completed_steps_in_reverse(){
  let steps=[CreateOrder,ReserveInventory,ProcessPayment,SendNotification];
  for(n,step)in steps.iter().enumerate(){
   let mut s=SagaOrchestrator{fail_at:Some(*step),..Default::default()};
   assert_eq!(run(s.execute_saga(order())),Err("Saga falhou e foi compensada".into()));
   let mut e=steps[..=n].iter().map(|x|(true,*x)).collect::<Vec<_>>();
   e.extend(steps[..n].iter().rev().map(|x|(false,*x)));
   assert_eq!(s.trace,e);
  }
 }
 #[test] fn failed_compensation_stops_and_surfaces_error(){
  let mut s=SagaOrchestrator{fail_at:Some(ProcessPayment),
   fail_undo:Some(ReserveInventory),..Default::default()};
  assert_eq!(run(s.execute_saga(order())),Err("Compensação falhou".into()));
  assert_eq!(s.trace.last(),Some(&(false,ReserveInventory)));
  assert!(!s.trace.contains(&(false,CreateOrder)));
 }
}
