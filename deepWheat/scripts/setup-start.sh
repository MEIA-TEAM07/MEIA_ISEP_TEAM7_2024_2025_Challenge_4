#!/bin/bash

USERS=(
  central
  field1
  field2
  field3
  payload1
  payload2
  vigilant1
  vigilant2
)

PASSWORD="admin1234"

for USER in "${USERS[@]}"; do
  echo "Creating user: $USER@localhost"
  sudo prosodyctl adduser "$USER@localhost" <<EOF
$PASSWORD
$PASSWORD
EOF
done

echo "All users created with password: $PASSWORD"