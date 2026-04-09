#!/bin/bash

# Script to load all Knative images
# Generated: 2026-04-09 13:35:45

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "Loading Knative images..."
echo "========================================="

echo "Loading eventing-controller..."
docker load -i "$SCRIPT_DIR/eventing-controller.tar"
docker tag eventing-controller:v1.21.2 harbor.idp.ecpk.ru/core/knative/eventing-controller:v1.21.2 2>/dev/null
echo "  ✓ eventing-controller loaded"

echo "Loading eventing-webhook..."
docker load -i "$SCRIPT_DIR/eventing-webhook.tar"
docker tag eventing-webhook:v1.21.2 harbor.idp.ecpk.ru/core/knative/eventing-webhook:v1.21.2 2>/dev/null
echo "  ✓ eventing-webhook loaded"

echo "Loading job-sink..."
docker load -i "$SCRIPT_DIR/job-sink.tar"
docker tag job-sink:v1.21.2 harbor.idp.ecpk.ru/core/knative/job-sink:v1.21.2 2>/dev/null
echo "  ✓ job-sink loaded"

echo "Loading pingsource-mt-adapter..."
docker load -i "$SCRIPT_DIR/pingsource-mt-adapter.tar"
docker tag pingsource-mt-adapter:v1.21.2 harbor.idp.ecpk.ru/core/knative/pingsource-mt-adapter:v1.21.2 2>/dev/null
echo "  ✓ pingsource-mt-adapter loaded"

echo "Loading request-reply..."
docker load -i "$SCRIPT_DIR/request-reply.tar"
docker tag request-reply:v1.21.2 harbor.idp.ecpk.ru/core/knative/request-reply:v1.21.2 2>/dev/null
echo "  ✓ request-reply loaded"

echo "Loading imc-controller..."
docker load -i "$SCRIPT_DIR/imc-controller.tar"
docker tag imc-controller:v1.21.2 harbor.idp.ecpk.ru/core/knative/imc-controller:v1.21.2 2>/dev/null
echo "  ✓ imc-controller loaded"

echo "Loading imc-dispatcher..."
docker load -i "$SCRIPT_DIR/imc-dispatcher.tar"
docker tag imc-dispatcher:v1.21.2 harbor.idp.ecpk.ru/core/knative/imc-dispatcher:v1.21.2 2>/dev/null
echo "  ✓ imc-dispatcher loaded"

echo "Loading mt-broker-controller..."
docker load -i "$SCRIPT_DIR/mt-broker-controller.tar"
docker tag mt-broker-controller:v1.21.2 harbor.idp.ecpk.ru/core/knative/mt-broker-controller:v1.21.2 2>/dev/null
echo "  ✓ mt-broker-controller loaded"

echo "Loading mt-broker-filter..."
docker load -i "$SCRIPT_DIR/mt-broker-filter.tar"
docker tag mt-broker-filter:v1.21.2 harbor.idp.ecpk.ru/core/knative/mt-broker-filter:v1.21.2 2>/dev/null
echo "  ✓ mt-broker-filter loaded"

echo "Loading mt-broker-ingress..."
docker load -i "$SCRIPT_DIR/mt-broker-ingress.tar"
docker tag mt-broker-ingress:v1.21.2 harbor.idp.ecpk.ru/core/knative/mt-broker-ingress:v1.21.2 2>/dev/null
echo "  ✓ mt-broker-ingress loaded"

echo "Loading kafka-controller..."
docker load -i "$SCRIPT_DIR/kafka-controller.tar"
docker tag kafka-controller:v1.21.2 harbor.idp.ecpk.ru/core/knative/kafka-controller:v1.21.2 2>/dev/null
echo "  ✓ kafka-controller loaded"

echo "Loading kafka-webhook..."
docker load -i "$SCRIPT_DIR/kafka-webhook.tar"
docker tag kafka-webhook:v1.21.2 harbor.idp.ecpk.ru/core/knative/kafka-webhook:v1.21.2 2>/dev/null
echo "  ✓ kafka-webhook loaded"

echo "Loading kafka-dispatcher..."
docker load -i "$SCRIPT_DIR/kafka-dispatcher.tar"
docker tag kafka-dispatcher:v1.21.2 harbor.idp.ecpk.ru/core/knative/kafka-dispatcher:v1.21.2 2>/dev/null
echo "  ✓ kafka-dispatcher loaded"

echo "Loading kafka-receiver..."
docker load -i "$SCRIPT_DIR/kafka-receiver.tar"
docker tag kafka-receiver:v1.21.2 harbor.idp.ecpk.ru/core/knative/kafka-receiver:v1.21.2 2>/dev/null
echo "  ✓ kafka-receiver loaded"

echo ""
echo "========================================="
echo "All images loaded successfully!"
echo "========================================="
