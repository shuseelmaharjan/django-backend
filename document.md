# Cronjob commands
To run CRONJOB for Batch Update: 
docker compose exec -T web python manage.py update_batch_statuses

To run CRONJOB for Fees Expiry Change: 
docker compose exec -T web python manage.py expire_fee_structures

