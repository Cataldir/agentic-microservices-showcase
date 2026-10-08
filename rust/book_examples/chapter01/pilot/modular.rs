pub mod users {
    pub struct User { pub id: u64 }
    pub fn create(name: &str) -> Result<User, &'static str> {
        if name.is_empty() { Err("Nome vazio") }
        else { Ok(User { id: 1 }) }
    }
}
pub mod orders {
    pub struct Order { pub id: u64, pub user_id: u64 }
    pub fn create(user: &super::users::User, amount: f64)
        -> Result<Order, &'static str>
    {
        if !amount.is_finite() || amount <= 0.0 {
            return Err("Valor inválido");
        }
        Ok(Order { id: 2, user_id: user.id })
    }
}
pub mod payments {
    pub struct Payment { pub id: u64, pub order_id: u64 }
    pub fn process(order: &super::orders::Order) -> Payment {
        Payment { id: 3, order_id: order.id }
    }
}
pub fn checkout(name: &str, amount: f64)
    -> Result<payments::Payment, &'static str>
{
    let user = users::create(name)?;
    let order = orders::create(&user, amount)?;
    let payment = payments::process(&order);
    Ok(payment)
}

#[cfg(test)]
mod tests {
 use super::*;
 #[test] fn valid_order_links_payment() {
  let p=checkout("Alice",99.99).unwrap();
  assert_eq!((p.id,p.order_id),(3,2));
 }
 #[test] fn rejects_empty_name() {
  assert_eq!(checkout("",99.99).err(),Some("Nome vazio"));
 }
 #[test] fn rejects_nonpositive_and_nonfinite_amounts() {
  for a in [0.0,-1.0,f64::NAN,f64::INFINITY] {
   assert_eq!(checkout("Alice",a).err(),Some("Valor inválido"));
  }
 }
}
