pub mod modular;
pub mod saga;
pub mod retry;
#[cfg(test)]
mod support {
 use std::{future::Future, sync::Arc, task::{Context, Poll, Wake, Waker}};
 struct Noop; impl Wake for Noop { fn wake(self: Arc<Self>) {} }
 pub fn run<F: Future>(future:F)->F::Output {
  let waker=Waker::from(Arc::new(Noop));let mut cx=Context::from_waker(&waker);
  let mut future=std::pin::pin!(future);
  loop {match future.as_mut().poll(&mut cx) {
   Poll::Ready(v)=>return v,Poll::Pending=>std::thread::yield_now(),
  }}
 }
}
