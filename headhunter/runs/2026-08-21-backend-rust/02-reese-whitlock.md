Subject: Rust settlement backend role at Kestrelbank (urn:li:person:e8mk2wpb)

Hi Reese,

I'm recruiting for Kestrelbank, a settlement infrastructure provider for Korean
e-commerce and fintech companies. Your profile caught my attention specifically
because of the reconciliation work at Finlogic Systems — rewriting the settlement
reconciler in Rust after it fell behind during month-end close, and building the
idempotency layer that lets the acquirer retry safely. That's almost exactly the
problem we're hiring for.

Our daily transaction volume has grown 40x in three years, and our settlement batch
(currently Python + Celery) keeps missing its closing window every quarter. We're
rewriting it in Rust, redesigning the reprocessing layer around idempotency and offset
management so a duplicate settlement never goes out, and moving the settlement tables
onto partitioned PostgreSQL with read replicas. Given you've already built the
authorization-path Rust service handling ~3,000 tx/sec and the exactly-once behavior
around it at Finlogic, I think this would be a very short ramp-up for you.

The role is based in our Seoul office, 3 days/week on-site. Would you be open to a
short call to talk through it?

Best,
Kestrelbank Recruiting
