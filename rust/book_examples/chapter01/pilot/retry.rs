use std::time::Duration;
#[allow(async_fn_in_trait)]
pub trait Waiter{async fn wait(&mut self,delay:Duration);}
pub struct RetryPolicy{
 pub max_retries:u32,pub initial_delay:Duration,pub max_delay:Duration,pub multiplier:f64,
}
impl Default for RetryPolicy{
 fn default()->Self{Self{max_retries:5,initial_delay:Duration::from_millis(100),
  max_delay:Duration::from_secs(30),multiplier:2.0}}
}
impl RetryPolicy{
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
                            "Falhou após {attempt} tentativas: {error}"));
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

}
#[cfg(test)]
mod tests{
 use super::*;use crate::support::run;
 #[derive(Default)]struct FakeWait{delays:Vec<Duration>}
 impl Waiter for FakeWait{async fn wait(&mut self,d:Duration){self.delays.push(d);}}
 #[test]fn immediate_success_does_not_wait(){
  let mut w=FakeWait::default();
  assert_eq!(run(RetryPolicy::default().execute(||Ok::<_,&str>(7),&mut w)),Ok(7));
  assert!(w.delays.is_empty());
 }
 #[test]fn third_attempt_waits_twice(){
  let mut c=0;let mut w=FakeWait::default();
  let value=run(RetryPolicy::default().execute(||{
   c+=1;if c<3{Err("transitório")}else{Ok("dados")}
  },&mut w));
  assert_eq!(value,Ok("dados"));assert_eq!(c,3);
  assert_eq!(w.delays,vec![Duration::from_millis(100),Duration::from_millis(200)]);
 }
 #[test]fn exhaustion_has_five_attempts_four_waits(){
  let mut c=0;let mut w=FakeWait::default();
  let value=run(RetryPolicy::default().execute(||{c+=1;Err::<(),_>("x")},&mut w));
  assert_eq!(c,5);assert!(value.unwrap_err().contains("5 tentativas"));
  assert_eq!(w.delays,vec![100,200,400,800].into_iter()
   .map(Duration::from_millis).collect::<Vec<_>>());
 }
 #[test]fn backoff_is_capped(){
  let mut w=FakeWait::default();
  let p=RetryPolicy{max_retries:6,initial_delay:Duration::from_secs(20),
   max_delay:Duration::from_secs(30),multiplier:2.0};
  let _=run(p.execute(||Err::<(),_>("x"),&mut w));
  assert_eq!(w.delays,vec![20,30,30,30,30].into_iter()
   .map(Duration::from_secs).collect::<Vec<_>>());
 }
}
