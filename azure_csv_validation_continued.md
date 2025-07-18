# Azure CSV Validation Solution - Testing & Operations Guide

## 🧪 Step 7: Testing the Solution

### 7.1 Create Test Data
```bash
# Create test CSV files locally
mkdir test-data
cd test-data

# Valid CSV file
cat > valid_customer_data.csv << 'EOF'
customer_id,name,email,registration_date,status
1,John Doe,john.doe@email.com,2023-01-15,active
2,Jane Smith,jane.smith@email.com,2023-02-20,active
3,Bob Johnson,bob.johnson@email.com,2023-03-10,inactive
4,Alice Brown,alice.brown@email.com,2023-04-05,active
5,Charlie Wilson,charlie.wilson@email.com,2023-05-12,active
EOF

# Invalid CSV file (missing data, malformed)
cat > invalid_customer_data.csv << 'EOF'
customer_id,name,email,registration_date,status
1,John Doe,john.doe@email.com,2023-01-15,active
2,Jane Smith,invalid-email,2023-02-20,active
3,,bob.johnson@email.com,2023-03-10,inactive
4,Alice Brown,alice.brown@email.com,INVALID_DATE,active
5,Charlie Wilson,charlie.wilson@email.com,2023-05-12,
EOF

# Large test file (for performance testing)
cat > large_test_data.csv << 'EOF'
id,value1,value2,value3,timestamp
EOF

# Generate large test data
for i in {1..10000}; do
    echo "$i,value_$i,test_data_$i,category_$((i % 10)),$(date -d "$i days ago" +%Y-%m-%d)" >> large_test_data.csv
done

# Empty file test
touch empty_file.csv

# Malformed CSV (inconsistent columns)
cat > malformed_structure.csv << 'EOF'
col1,col2,col3
value1,value2,value3
value4,value5
value6,value7,value8,value9
EOF
```

### 7.2 Upload Test Files to Storage
```bash
# Upload valid test file
az storage blob upload \
    --account-name $STORAGE_ACCOUNT \
    --container-name raw-data \
    --name "valid_customer_data.csv" \
    --file "valid_customer_data.csv" \
    --account-key $STORAGE_KEY

# Upload invalid test file
az storage blob upload \
    --account-name $STORAGE_ACCOUNT \
    --container-name raw-data \
    --name "invalid_customer_data.csv" \
    --file "invalid_customer_data.csv" \
    --account-key $STORAGE_KEY

# Upload large test file
az storage blob upload \
    --account-name $STORAGE_ACCOUNT \
    --container-name raw-data \
    --name "large_test_data.csv" \
    --file "large_test_data.csv" \
    --account-key $STORAGE_KEY

# Upload empty file
az storage blob upload \
    --account-name $STORAGE_ACCOUNT \
    --container-name raw-data \
    --name "empty_file.csv" \
    --file "empty_file.csv" \
    --account-key $STORAGE_KEY

# Upload malformed file
az storage blob upload \
    --account-name $STORAGE_ACCOUNT \
    --container-name raw-data \
    --name "malformed_structure.csv" \
    --file "malformed_structure.csv" \
    --account-key $STORAGE_KEY
```

### 7.3 Test Azure Function Directly
```bash
# Get function key
FUNCTION_KEY=$(az functionapp keys list \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --query functionKeys.default -o tsv)

# Test valid CSV
curl -X POST \
    -H "Content-Type: application/json" \
    -H "x-functions-key: $FUNCTION_KEY" \
    -d '{"container_name": "raw-data", "blob_name": "valid_customer_data.csv"}' \
    "https://$FUNCTION_APP.azurewebsites.net/api/csv_validator"

# Test invalid CSV
curl -X POST \
    -H "Content-Type: application/json" \
    -H "x-functions-key: $FUNCTION_KEY" \
    -d '{"container_name": "raw-data", "blob_name": "invalid_customer_data.csv"}' \
    "https://$FUNCTION_APP.azurewebsites.net/api/csv_validator"

# Test large file
curl -X POST \
    -H "Content-Type: application/json" \
    -H "x-functions-key: $FUNCTION_KEY" \
    -d '{"container_name": "raw-data", "blob_name": "large_test_data.csv"}' \
    "https://$FUNCTION_APP.azurewebsites.net/api/csv_validator"
```

### 7.4 Test Data Factory Pipeline
```bash
# Test pipeline with valid file
az datafactory pipeline create-run \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --name "CSV_Validation_Pipeline" \
    --parameters container_name="raw-data" blob_name="valid_customer_data.csv"

# Test pipeline with invalid file
az datafactory pipeline create-run \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --name "CSV_Validation_Pipeline" \
    --parameters container_name="raw-data" blob_name="invalid_customer_data.csv"

# Monitor pipeline runs
az datafactory pipeline-run query-by-factory \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --last-updated-after "2024-01-01T00:00:00Z" \
    --last-updated-before "2024-12-31T23:59:59Z"
```

### 7.5 Create Automated Test Script
Create `test_validation_solution.py`:
```python
#!/usr/bin/env python3
"""
Automated test script for Azure CSV Validation Solution
"""

import requests
import json
import time
import sys
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import os

class ValidationTester:
    def __init__(self, function_url, function_key, storage_account_name):
        self.function_url = function_url
        self.function_key = function_key
        self.storage_account_name = storage_account_name
        self.blob_service_client = BlobServiceClient(
            account_url=f"https://{storage_account_name}.blob.core.windows.net",
            credential=DefaultAzureCredential()
        )
        
    def test_function_validation(self, container_name, blob_name, expected_valid=True):
        """Test Azure Function validation"""
        headers = {
            'Content-Type': 'application/json',
            'x-functions-key': self.function_key
        }
        
        payload = {
            'container_name': container_name,
            'blob_name': blob_name
        }
        
        try:
            response = requests.post(
                f"{self.function_url}/api/csv_validator",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            result = response.json()
            
            print(f"\n--- Testing {blob_name} ---")
            print(f"Expected valid: {expected_valid}")
            print(f"Actual valid: {result.get('is_valid', False)}")
            print(f"Status code: {response.status_code}")
            print(f"Errors: {result.get('errors', [])}")
            print(f"Warnings: {result.get('warnings', [])}")
            print(f"Stats: {json.dumps(result.get('stats', {}), indent=2)}")
            
            # Validate result
            if result.get('is_valid') == expected_valid:
                print("✅ Test PASSED")
                return True
            else:
                print("❌ Test FAILED")
                return False
                
        except Exception as e:
            print(f"❌ Test ERROR: {str(e)}")
            return False
    
    def check_file_moved(self, source_container, target_container, blob_name):
        """Check if file was moved to correct container"""
        try:
            target_blob = self.blob_service_client.get_blob_client(
                container=target_container,
                blob=blob_name
            )
            
            if target_blob.exists():
                print(f"✅ File found in {target_container} container")
                return True
            else:
                print(f"❌ File NOT found in {target_container} container")
                return False
                
        except Exception as e:
            print(f"❌ Error checking file location: {str(e)}")
            return False
    
    def run_comprehensive_tests(self):
        """Run all validation tests"""
        print("🧪 Starting Azure CSV Validation Tests...")
        
        test_cases = [
            ("raw-data", "valid_customer_data.csv", True),
            ("raw-data", "invalid_customer_data.csv", False),
            ("raw-data", "large_test_data.csv", True),
            ("raw-data", "empty_file.csv", False),
            ("raw-data", "malformed_structure.csv", False),
        ]
        
        results = []
        
        for container, blob_name, expected_valid in test_cases:
            result = self.test_function_validation(container, blob_name, expected_valid)
            results.append(result)
            
            # Wait a bit between tests
            time.sleep(2)
        
        # Summary
        passed = sum(results)
        total = len(results)
        
        print(f"\n📊 Test Summary:")
        print(f"Passed: {passed}/{total}")
        print(f"Success rate: {passed/total*100:.1f}%")
        
        if passed == total:
            print("🎉 All tests PASSED!")
            return True
        else:
            print("⚠️  Some tests FAILED!")
            return False

def main():
    # Configuration (replace with your actual values)
    FUNCTION_APP_NAME = os.getenv('FUNCTION_APP_NAME', 'your-function-app')
    FUNCTION_KEY = os.getenv('FUNCTION_KEY', 'your-function-key')
    STORAGE_ACCOUNT = os.getenv('STORAGE_ACCOUNT', 'your-storage-account')
    
    function_url = f"https://{FUNCTION_APP_NAME}.azurewebsites.net"
    
    # Initialize tester
    tester = ValidationTester(function_url, FUNCTION_KEY, STORAGE_ACCOUNT)
    
    # Run tests
    success = tester.run_comprehensive_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

Make the script executable and run it:
```bash
chmod +x test_validation_solution.py

# Set environment variables
export FUNCTION_APP_NAME=$FUNCTION_APP
export FUNCTION_KEY=$FUNCTION_KEY
export STORAGE_ACCOUNT=$STORAGE_ACCOUNT

# Run tests
python3 test_validation_solution.py
```

## 🔧 Step 8: Production Configuration

### 8.1 Configure Security
```bash
# Enable Function App authentication
az functionapp auth update \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --enabled true \
    --action RedirectToLoginPage \
    --aad-client-id "your-app-registration-client-id" \
    --aad-client-secret "your-app-registration-secret"

# Configure network restrictions
az functionapp config access-restriction add \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --rule-name "AllowDataFactory" \
    --action Allow \
    --ip-address "0.0.0.0/0" \
    --priority 100
```

### 8.2 Configure Backup and Disaster Recovery
```bash
# Enable backup for Function App
az functionapp config backup create \
    --resource-group $RESOURCE_GROUP \
    --webapp-name $FUNCTION_APP \
    --container-url "https://$STORAGE_ACCOUNT.blob.core.windows.net/backups" \
    --backup-name "daily-backup" \
    --frequency 1440 \
    --retention-period 30

# Configure geo-redundancy for storage
az storage account update \
    --name $STORAGE_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --sku Standard_GRS
```

### 8.3 Set up Log Analytics Workspace
```bash
# Create Log Analytics workspace
az monitor log-analytics workspace create \
    --workspace-name "csv-validation-logs" \
    --resource-group $RESOURCE_GROUP \
    --location "East US"

# Get workspace ID
WORKSPACE_ID=$(az monitor log-analytics workspace show \
    --workspace-name "csv-validation-logs" \
    --resource-group $RESOURCE_GROUP \
    --query customerId -o tsv)

# Configure diagnostic settings
az monitor diagnostic-settings create \
    --name "function-app-logs" \
    --resource $(az functionapp show --name $FUNCTION_APP --resource-group $RESOURCE_GROUP --query id -o tsv) \
    --workspace $WORKSPACE_ID \
    --logs '[{"category": "FunctionAppLogs", "enabled": true}]' \
    --metrics '[{"category": "AllMetrics", "enabled": true}]'
```

## 📊 Step 9: Monitoring and Maintenance

### 9.1 Create Custom Dashboards
Create `dashboard.json`:
```json
{
    "lenses": {
        "0": {
            "order": 0,
            "parts": {
                "0": {
                    "position": {"x": 0, "y": 0, "colSpan": 6, "rowSpan": 4},
                    "metadata": {
                        "inputs": [{
                            "name": "queryInputs",
                            "value": {
                                "query": "traces | where message contains 'CSV' | summarize count() by bin(timestamp, 1h)",
                                "timespan": "PT24H"
                            }
                        }],
                        "type": "Extension/AppInsightsExtension/PartType/AnalyticsLineChartPart"
                    }
                },
                "1": {
                    "position": {"x": 6, "y": 0, "colSpan": 6, "rowSpan": 4},
                    "metadata": {
                        "inputs": [{
                            "name": "queryInputs",
                            "value": {
                                "query": "customEvents | where name == 'ValidationResult' | extend Status = tostring(customDimensions.is_valid) | summarize count() by Status",
                                "timespan": "PT24H"
                            }
                        }],
                        "type": "Extension/AppInsightsExtension/PartType/AnalyticsPieChartPart"
                    }
                }
            }
        }
    }
}
```

### 9.2 Set Up Performance Monitoring
```bash
# Create KQL queries for monitoring
cat > monitoring_queries.kql << 'EOF'
// Validation success rate
customEvents
| where name == "ValidationResult"
| extend IsValid = tobool(customDimensions.is_valid)
| summarize 
    Total = count(),
    Successful = countif(IsValid == true),
    Failed = countif(IsValid == false)
| extend SuccessRate = round(Successful * 100.0 / Total, 2)

// Average processing time
requests
| where name == "csv_validator"
| summarize avg(duration) by bin(timestamp, 1h)

// Error analysis
exceptions
| where outerMessage contains "validation"
| summarize count() by outerMessage
| order by count_ desc

// File size distribution
customEvents
| where name == "ValidationResult"
| extend FileSizeMB = todouble(customDimensions.file_size_mb)
| summarize count() by bin(FileSizeMB, 10)
EOF
```

### 9.3 Create Maintenance Scripts
Create `maintenance.sh`:
```bash
#!/bin/bash
# Maintenance script for CSV Validation Solution

echo "🔧 Starting maintenance tasks..."

# Clean up old files (older than 30 days)
echo "Cleaning up old files..."
az storage blob delete-batch \
    --account-name $STORAGE_ACCOUNT \
    --source "validated-data" \
    --if-older-than "30"

az storage blob delete-batch \
    --account-name $STORAGE_ACCOUNT \
    --source "error-data" \
    --if-older-than "30"

# Check Function App health
echo "Checking Function App health..."
HEALTH_STATUS=$(az functionapp show \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --query state -o tsv)

if [ "$HEALTH_STATUS" != "Running" ]; then
    echo "⚠️  Function App is not running. Status: $HEALTH_STATUS"
    # Restart Function App
    az functionapp restart \
        --name $FUNCTION_APP \
        --resource-group $RESOURCE_GROUP
else
    echo "✅ Function App is healthy"
fi

# Check Data Factory status
echo "Checking Data Factory status..."
RECENT_RUNS=$(az datafactory pipeline-run query-by-factory \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --last-updated-after "$(date -d '1 day ago' -u +%Y-%m-%dT%H:%M:%SZ)" \
    --query "length(value[?status=='Failed'])")

if [ "$RECENT_RUNS" -gt 0 ]; then
    echo "⚠️  Found $RECENT_RUNS failed pipeline runs in the last 24 hours"
else
    echo "✅ No failed pipeline runs in the last 24 hours"
fi

# Generate health report
echo "Generating health report..."
cat > health_report.txt << EOF
CSV Validation Solution Health Report
Generated: $(date)

Function App Status: $HEALTH_STATUS
Failed Pipeline Runs (24h): $RECENT_RUNS

Storage Account Usage:
$(az storage account show-usage --account-name $STORAGE_ACCOUNT --query "{used: usedCapacity, limit: limit}")

Recent Activity:
$(az monitor activity-log list \
    --resource-group $RESOURCE_GROUP \
    --start-time "$(date -d '1 day ago' -u +%Y-%m-%dT%H:%M:%SZ)" \
    --query "[?contains(resourceId, '$FUNCTION_APP') || contains(resourceId, '$DATA_FACTORY')].{time: eventTimestamp, status: status.value, operation: operationName.value}" \
    --output table)
EOF

echo "✅ Maintenance tasks completed"
```

Make it executable:
```bash
chmod +x maintenance.sh
```

### 9.4 Set Up Automated Alerts
```bash
# Create alert for high error rate
az monitor metrics alert create \
    --name "High_Validation_Error_Rate" \
    --resource-group $RESOURCE_GROUP \
    --scopes "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP" \
    --condition "avg requests/failed > 5" \
    --description "Alert when validation error rate is high" \
    --evaluation-frequency 5m \
    --window-size 15m \
    --severity 2 \
    --action-group-id "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Insights/actionGroups/CSV_Validation_Actions"

# Create alert for function app downtime
az monitor metrics alert create \
    --name "Function_App_Downtime" \
    --resource-group $RESOURCE_GROUP \
    --scopes "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP" \
    --condition "avg Http5xx > 0" \
    --description "Alert when function app is down" \
    --evaluation-frequency 1m \
    --window-size 5m \
    --severity 1 \
    --action-group-id "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Insights/actionGroups/CSV_Validation_Actions"
```

## 🚀 Step 10: Production Deployment Checklist

### 10.1 Pre-Production Checklist
```bash
# Create checklist script
cat > pre_production_checklist.sh << 'EOF'
#!/bin/bash
echo "📋 Pre-Production Deployment Checklist"
echo "======================================"

# Check 1: All resources created
echo "1. Checking resource creation..."
RESOURCES=(
    "Microsoft.Storage/storageAccounts"
    "Microsoft.Web/sites"
    "Microsoft.DataFactory/factories"
    "Microsoft.Insights/components"
    "Microsoft.KeyVault/vaults"
)

for resource in "${RESOURCES[@]}"; do
    count=$(az resource list --resource-group $RESOURCE_GROUP --resource-type $resource --query "length(@)")
    if [ $count -gt 0 ]; then
        echo "✅ $resource: $count found"
    else
        echo "❌ $resource: None found"
    fi
done

# Check 2: Function deployment
echo "2. Checking function deployment..."
FUNCTION_STATUS=$(az functionapp show --name $FUNCTION_APP --resource-group $RESOURCE_GROUP --query state -o tsv)
if [ "$FUNCTION_STATUS" == "Running" ]; then
    echo "✅ Function App is running"
else
    echo "❌ Function App status: $FUNCTION_STATUS"
fi

# Check 3: Storage containers
echo "3. Checking storage containers..."
CONTAINERS=("raw-data" "validated-data" "error-data" "staging")
for container in "${CONTAINERS[@]}"; do
    if az storage container exists --name $container --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY --query exists -o tsv | grep -q true; then
        echo "✅ Container $container exists"
    else
        echo "❌ Container $container missing"
    fi
done

# Check 4: Data Factory pipeline
echo "4. Checking Data Factory pipeline..."
PIPELINE_COUNT=$(az datafactory pipeline list --resource-group $RESOURCE_GROUP --factory-name $DATA_FACTORY --query "length(@)")
if [ $PIPELINE_COUNT -gt 0 ]; then
    echo "✅ Data Factory pipeline exists"
else
    echo "❌ No Data Factory pipeline found"
fi

# Check 5: Monitoring setup
echo "5. Checking monitoring setup..."
ALERT_COUNT=$(az monitor metrics alert list --resource-group $RESOURCE_GROUP --query "length(@)")
if [ $ALERT_COUNT -gt 0 ]; then
    echo "✅ Monitoring alerts configured ($ALERT_COUNT found)"
else
    echo "⚠️  No monitoring alerts found"
fi

echo "======================================"
echo "✅ Pre-production checklist completed"
EOF

chmod +x pre_production_checklist.sh
./pre_production_checklist.sh
```

### 10.2 Go-Live Steps
```bash
# 1. Final configuration
echo "🚀 Configuring production settings..."

# Set production app settings
az functionapp config appsettings set \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "ENVIRONMENT=production" \
        "LOG_LEVEL=INFO" \
        "MAX_FILE_SIZE_MB=500" \
        "ENABLE_DETAILED_LOGGING=true"

# 2. Enable production monitoring
az monitor diagnostic-settings create \
    --name "production-diagnostics" \
    --resource $(az functionapp show --name $FUNCTION_APP --resource-group $RESOURCE_GROUP --query id -o tsv) \
    --workspace $(az monitor log-analytics workspace show --workspace-name "csv-validation-logs" --resource-group $RESOURCE_GROUP --query id -o tsv) \
    --logs '[{"category": "FunctionAppLogs", "enabled": true, "retentionPolicy": {"days": 30, "enabled": true}}]' \
    --metrics '[{"category": "AllMetrics", "enabled": true, "retentionPolicy": {"days": 30, "enabled": true}}]'

# 3. Create production schedule
az datafactory trigger create \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --name "DailyValidationTrigger" \
    --properties '{
        "type": "ScheduleTrigger",
        "typeProperties": {
            "recurrence": {
                "frequency": "Day",
                "interval": 1,
                "startTime": "2024-01-01T02:00:00Z",
                "timeZone": "UTC"
            }
        }
    }'

echo "✅ Production deployment completed!"
echo "📊 Monitor your solution at: https://portal.azure.com"
```

## 📚 Documentation and Support

### 10.3 Create User Documentation
```markdown
# CSV Validation Solution - User Guide

## Overview
This solution validates CSV files uploaded to Azure Storage and moves them to appropriate containers based on validation results.

## How to Use
1. Upload CSV files to the `raw-data` container
2. The system automatically validates the files
3. Valid files are moved to `validated-data`
4. Invalid files are moved to `error-data`

## Validation Rules
- Maximum file size: 500MB
- Required: Valid CSV structure
- Encoding: UTF-8 recommended
- Headers: Must be present in first row

## Monitoring
- Check Azure Monitor for validation metrics
- Review Application Insights for detailed logs
- Set up alerts for critical failures

## Troubleshooting
- Check function logs in Application Insights
- Verify storage account permissions
- Ensure Data Factory pipeline is enabled
```

### 10.4 Create Operations Runbook
```markdown
# CSV Validation Solution - Operations Runbook

## Daily Operations
1. Check health dashboard
2. Review validation metrics
3. Monitor error rates
4. Check storage usage

## Weekly Operations
1. Run maintenance script
2. Review alert configurations
3. Check backup status
4. Update documentation

## Monthly Operations
1. Review and optimize costs
2. Update function dependencies
3. Review security configurations
4. Capacity planning review

## Incident Response
1. Check function app status
2. Review recent pipeline runs
3. Check storage account health
4. Escalate if needed
```

This completes the comprehensive Azure CSV Validation Solution deployment guide. The solution is now ready for production use with proper monitoring, maintenance, and documentation in place.