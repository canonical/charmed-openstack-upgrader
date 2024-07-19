# How to query nova db for soft deleted instances

This is useful for verifying or debugging archive and purge steps.
Instructions below detail how to connect to the nova database and query common information for soft deleted instances.

## Credentials

First you'll need the MySQL user password:

```sh
PASS="$(juju exec --unit mysql-innodb-cluster/leader -- leader-get cluster-password)"
echo "$PASS"
```

## SQL reference

The main tables to work with are `nova.instances` for the active table,
and `nova.shadow_instances` for the shadow table.

A non-deleted instance will have the `deleted` column set to `0` or `NULL`.
So far, `NULL` values have not been observed in practice.
When an instance is soft-deleted,
the `deleted` column will be set to a non-zero integer.

**List** soft deleted instances in the **active** table:

```sql
select uuid, display_name from nova.instances where deleted != 0;
```

**List** soft deleted instances in the **shadow** table:

(`deleted != 0` probably isn't necessary, because the shadow table should only contain soft deleted instances)

```sql
select uuid, display_name from nova.shadow_instances where deleted != 0;
```

**Count** soft deleted instances in the **active** table:

```sql
select count(*) from nova.instances where deleted != 0;
```

**Count** soft deleted instances in the **shadow** table:

```sql
select count(*) from nova.shadow_instances where deleted != 0;
```

## Interactive

SSH in to an interactive MySQL shell, connected to the MySQL server:

```sh
juju ssh mysql-innodb-cluster/leader sudo mysql -u clusteruser -h localhost "-p$PASS"
```

Now once you're in, you can reference the SQL examples above to query as desired.

## Batch

For a non-interactive batch mode, you can pipe the SQL to the MySQL command through juju ssh.
For example:

```sh
echo "select uuid, display_name from nova.instances where deleted != 0;" | juju ssh mysql-innodb-cluster/leader sudo mysql -u clusteruser -h localhost "-p$PASS"
```

Refer to the earlier SQL examples to query as desired.
