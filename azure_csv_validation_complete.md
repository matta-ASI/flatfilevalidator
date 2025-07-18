# Azure CSV Validation Solution - Complete Deployment Guide

## 📋 Prerequisites

### Required Tools
- **Azure CLI** (version 2.0 or later)
- **Azure PowerShell** (optional, for PowerShell users)
- **Python 3.9+** (for local development/testing)
- **Visual Studio Code** with Azure extensions
- **Git** for version control

### Azure Subscription Requirements
- **Azure Subscription** with sufficient permissions
- **Resource Group** creation permissions
- **Service Principal** for deployments (optional but recommended)

### Required Azure Services
- Azure Data Factory
- Azure Functions
- Azure Storage Account
- Azure Monitor/Application Insights
- Azure Key Vault (for secrets)

## 🎯 Step 1: Environment Setup

### 1.1 Install Azure CLI
```bash
# Windows (using winget)
winget install Microsoft.AzureCLI

# macOS (using homebrew)
brew install azure-cli

# Linux (Ubuntu/Debian)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### 1.2 Login to Azure
```bash
# Login interactively
az login

# Set default subscription
az account set --subscription "your-subscription-id"

# Verify login
az account show
```

### 1.3 Create Resource Group
```bash
# Set variables
RESOURCE_GROUP="rg-csv-validation"
LOCATION="East US"

# Create resource group
az group create \
    --name $RESOURCE_GROUP \
    --location "$LOCATION"
```

### 1.4 Register Required Resource Providers
```bash
# Register required providers
az provider register --namespace Microsoft.DataFactory
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.Insights
az provider register --namespace Microsoft.KeyVault
```

## 🏗️ Step 2: Deploy Core Infrastructure

### 2.1 Create ARM Template File
Create `infrastructure.json`:

```json
{
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "projectName": {
            "type": "string",
            "defaultValue": "csvvalidation",
            "metadata": {
                "description": "Base name for all resources"
            }
        },
        "location": {
            "type": "string",
            "defaultValue": "[resourceGroup().location]",
            "metadata": {
                "description": "Location for all resources"
            }
        }
    },
    "variables": {
        "storageAccountName": "[concat(parameters('projectName'), 'storage', uniqueString(resourceGroup().id))]",
        "functionAppName": "[concat(parameters('projectName'), '-func-', uniqueString(resourceGroup().id))]",
        "dataFactoryName": "[concat(parameters('projectName'), '-adf-', uniqueString(resourceGroup().id))]",
        "appInsightsName": "[concat(parameters('projectName'), '-ai-', uniqueString(resourceGroup().id))]",
        "keyVaultName": "[concat(parameters('projectName'), '-kv-', uniqueString(resourceGroup().id))]",
        "hostingPlanName": "[concat(parameters('projectName'), '-plan-', uniqueString(resourceGroup().id))]"
    },
    "resources": [
        {
            "type": "Microsoft.Storage/storageAccounts",
            "apiVersion": "2021-08-01",
            "name": "[variables('storageAccountName')]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "Standard_LRS"
            },
            "kind": "StorageV2",
            "properties": {
                "supportsHttpsTrafficOnly": true,
                "minimumTlsVersion": "TLS1_2"
            }
        },
        {
            "type": "Microsoft.Web/serverfarms",
            "apiVersion": "2021-02-01",
            "name": "[variables('hostingPlanName')]",
            "location": "[parameters('location')]",
            "sku": {
                "name": "Y1",
                "tier": "Dynamic"
            },
            "kind": "functionapp",
            "properties": {
                "reserved": true
            }
        },
        {
            "type": "Microsoft.Insights/components",
            "apiVersion": "2020-02-02",
            "name": "[variables('appInsightsName')]",
            "location": "[parameters('location')]",
            "kind": "web",
            "properties": {
                "Application_Type": "web"
            }
        },
        {
            "type": "Microsoft.Web/sites",
            "apiVersion": "2021-02-01",
            "name": "[variables('functionAppName')]",
            "location": "[parameters('location')]",
            "kind": "functionapp,linux",
            "dependsOn": [
                "[resourceId('Microsoft.Web/serverfarms', variables('hostingPlanName'))]",
                "[resourceId('Microsoft.Storage/storageAccounts', variables('storageAccountName'))]",
                "[resourceId('Microsoft.Insights/components', variables('appInsightsName'))]"
            ],
            "identity": {
                "type": "SystemAssigned"
            },
            "properties": {
                "serverFarmId": "[resourceId('Microsoft.Web/serverfarms', variables('hostingPlanName'))]",
                "siteConfig": {
                    "linuxFxVersion": "Python|3.9",
                    "appSettings": [
                        {
                            "name": "FUNCTIONS_EXTENSION_VERSION",
                            "value": "~4"
                        },
                        {
                            "name": "FUNCTIONS_WORKER_RUNTIME",
                            "value": "python"
                        },
                        {
                            "name": "AzureWebJobsStorage",
                            "value": "[concat('DefaultEndpointsProtocol=https;AccountName=', variables('storageAccountName'), ';AccountKey=', listKeys(resourceId('Microsoft.Storage/storageAccounts', variables('storageAccountName')), '2021-08-01').keys[0].value)]"
                        },
                        {
                            "name": "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING",
                            "value": "[concat('DefaultEndpointsProtocol=https;AccountName=', variables('storageAccountName'), ';AccountKey=', listKeys(resourceId('Microsoft.Storage/storageAccounts', variables('storageAccountName')), '2021-08-01').keys[0].value)]"
                        },
                        {
                            "name": "APPINSIGHTS_INSTRUMENTATIONKEY",
                            "value": "[reference(resourceId('Microsoft.Insights/components', variables('appInsightsName'))).InstrumentationKey]"
                        },
                        {
                            "name": "STORAGE_ACCOUNT_URL",
                            "value": "[reference(resourceId('Microsoft.Storage/storageAccounts', variables('storageAccountName'))).primaryEndpoints.blob]"
                        }
                    ]
                }
            }
        },
        {
            "type": "Microsoft.KeyVault/vaults",
            "apiVersion": "2021-10-01",
            "name": "[variables('keyVaultName')]",
            "location": "[parameters('location')]",
            "dependsOn": [
                "[resourceId('Microsoft.Web/sites', variables('functionAppName'))]"
            ],
            "properties": {
                "tenantId": "[subscription().tenantId]",
                "sku": {
                    "name": "standard",
                    "family": "A"
                },
                "accessPolicies": [
                    {
                        "tenantId": "[subscription().tenantId]",
                        "objectId": "[reference(resourceId('Microsoft.Web/sites', variables('functionAppName')), '2021-02-01', 'Full').identity.principalId]",
                        "permissions": {
                            "secrets": ["get", "list"]
                        }
                    }
                ]
            }
        },
        {
            "type": "Microsoft.DataFactory/factories",
            "apiVersion": "2018-06-01",
            "name": "[variables('dataFactoryName')]",
            "location": "[parameters('location')]",
            "identity": {
                "type": "SystemAssigned"
            },
            "properties": {}
        }
    ],
    "outputs": {
        "storageAccountName": {
            "type": "string",
            "value": "[variables('storageAccountName')]"
        },
        "functionAppName": {
            "type": "string",
            "value": "[variables('functionAppName')]"
        },
        "dataFactoryName": {
            "type": "string",
            "value": "[variables('dataFactoryName')]"
        },
        "appInsightsName": {
            "type": "string",
            "value": "[variables('appInsightsName')]"
        },
        "keyVaultName": {
            "type": "string",
            "value": "[variables('keyVaultName')]"
        }
    }
}
```

### 2.2 Deploy Infrastructure
```bash
# Deploy ARM template
az deployment group create \
    --resource-group $RESOURCE_GROUP \
    --template-file infrastructure.json \
    --parameters projectName="csvvalidation"

# Get deployment outputs
STORAGE_ACCOUNT=$(az deployment group show \
    --resource-group $RESOURCE_GROUP \
    --name infrastructure \
    --query properties.outputs.storageAccountName.value -o tsv)

FUNCTION_APP=$(az deployment group show \
    --resource-group $RESOURCE_GROUP \
    --name infrastructure \
    --query properties.outputs.functionAppName.value -o tsv)

DATA_FACTORY=$(az deployment group show \
    --resource-group $RESOURCE_GROUP \
    --name infrastructure \
    --query properties.outputs.dataFactoryName.value -o tsv)

echo "Storage Account: $STORAGE_ACCOUNT"
echo "Function App: $FUNCTION_APP"
echo "Data Factory: $DATA_FACTORY"
```

## 🔧 Step 3: Create Storage Containers

### 3.1 Create Required Containers
```bash
# Get storage account key
STORAGE_KEY=$(az storage account keys list \
    --resource-group $RESOURCE_GROUP \
    --account-name $STORAGE_ACCOUNT \
    --query '[0].value' -o tsv)

# Create containers
az storage container create \
    --name "raw-data" \
    --account-name $STORAGE_ACCOUNT \
    --account-key $STORAGE_KEY

az storage container create \
    --name "validated-data" \
    --account-name $STORAGE_ACCOUNT \
    --account-key $STORAGE_KEY

az storage container create \
    --name "error-data" \
    --account-name $STORAGE_ACCOUNT \
    --account-key $STORAGE_KEY

az storage container create \
    --name "staging" \
    --account-name $STORAGE_ACCOUNT \
    --account-key $STORAGE_KEY
```

## 🚀 Step 4: Deploy Azure Function

### 4.1 Create Function Project Structure
```bash
# Create project directory
mkdir csv-validation-function
cd csv-validation-function

# Create function structure
mkdir -p csv_validator
mkdir -p shared

# Create requirements.txt
cat > requirements.txt << 'EOF'
azure-functions>=1.11.0
azure-storage-blob>=12.14.0
azure-identity>=1.12.0
azure-keyvault-secrets>=4.6.0
azure-monitor-opentelemetry>=1.0.0
pandas>=1.5.0
chardet>=5.0.0
opentelemetry-instrumentation-logging>=0.38b0
EOF

# Create host.json
cat > host.json << 'EOF'
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "excludedTypes": "Request"
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[3.*, 4.0.0)"
  },
  "functionTimeout": "00:10:00"
}
EOF

# Create local.settings.json (for local development)
cat > local.settings.json << 'EOF'
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "STORAGE_ACCOUNT_URL": "",
    "APPINSIGHTS_INSTRUMENTATIONKEY": ""
  }
}
EOF
```

### 4.2 Create Function Code Files

Create `csv_validator/__init__.py`:
```python
import azure.functions as func
import json
import pandas as pd
import logging
import io
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import os
from datetime import datetime
import chardet
from typing import Dict, Any

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function entry point for CSV validation
    """
    logging.info('CSV Validation function triggered')
    
    try:
        # Parse request
        req_body = req.get_json()
        container_name = req_body.get('container_name')
        blob_name = req_body.get('blob_name')
        
        if not container_name or not blob_name:
            return func.HttpResponse(
                json.dumps({'error': 'Missing container_name or blob_name'}),
                status_code=400,
                mimetype='application/json'
            )
        
        # Initialize validator
        validator = CSVValidator()
        result = validator.validate_csv_comprehensive(container_name, blob_name)
        
        # Return result
        return func.HttpResponse(
            json.dumps(result),
            status_code=200 if result['is_valid'] else 400,
            mimetype='application/json'
        )
        
    except Exception as e:
        logging.error(f'Validation error: {str(e)}')
        return func.HttpResponse(
            json.dumps({'error': str(e)}),
            status_code=500,
            mimetype='application/json'
        )

class CSVValidator:
    """Azure Function CSV Validator"""
    
    def __init__(self):
        self.credential = DefaultAzureCredential()
        self.blob_service_client = BlobServiceClient(
            account_url=os.environ.get('STORAGE_ACCOUNT_URL'),
            credential=self.credential
        )
    
    def validate_csv_comprehensive(self, container_name: str, blob_name: str) -> Dict[str, Any]:
        """Comprehensive CSV validation"""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'stats': {},
            'timestamp': datetime.utcnow().isoformat(),
            'blob_path': f"{container_name}/{blob_name}"
        }
        
        try:
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, 
                blob=blob_name
            )
            
            # Get blob properties
            blob_properties = blob_client.get_blob_properties()
            file_size_mb = blob_properties.size / (1024 * 1024)
            
            validation_result['stats']['file_size_mb'] = round(file_size_mb, 2)
            validation_result['stats']['last_modified'] = blob_properties.last_modified.isoformat()
            
            # Size validation
            if file_size_mb > 500:
                validation_result['errors'].append(f"File size {file_size_mb:.2f}MB exceeds 500MB limit")
                validation_result['is_valid'] = False
                return validation_result
            
            # Download and validate content
            blob_data = blob_client.download_blob().readall()
            
            # Encoding detection
            encoding_result = chardet.detect(blob_data[:10000])
            encoding = encoding_result['encoding'] or 'utf-8'
            confidence = encoding_result['confidence']
            
            validation_result['stats']['encoding'] = encoding
            validation_result['stats']['encoding_confidence'] = confidence
            
            if confidence < 0.7:
                validation_result['warnings'].append(f"Low encoding confidence: {confidence:.2f}")
            
            # Convert to string for pandas
            try:
                csv_content = blob_data.decode(encoding)
            except UnicodeDecodeError:
                validation_result['errors'].append(f"Cannot decode file with encoding: {encoding}")
                validation_result['is_valid'] = False
                return validation_result
            
            # Pandas validation
            try:
                df = pd.read_csv(io.StringIO(csv_content), low_memory=False)
                
                # Basic stats
                validation_result['stats']['row_count'] = len(df)
                validation_result['stats']['column_count'] = len(df.columns)
                validation_result['stats']['columns'] = df.columns.tolist()
                
                # Data quality checks
                self._perform_data_quality_checks(df, validation_result)
                
            except Exception as e:
                validation_result['errors'].append(f"Pandas parsing error: {str(e)}")
                validation_result['is_valid'] = False
                
        except Exception as e:
            validation_result['errors'].append(f"Validation error: {str(e)}")
            validation_result['is_valid'] = False
            
        return validation_result
    
    def _perform_data_quality_checks(self, df: pd.DataFrame, result: Dict[str, Any]):
        """Perform data quality checks"""
        
        # Null analysis
        null_analysis = {}
        for col in df.columns:
            null_count = df[col].isnull().sum()
            null_pct = null_count / len(df)
            null_analysis[col] = {
                'null_count': null_count,
                'null_percentage': round(null_pct, 4)
            }
            
            if null_pct > 0.5:
                result['warnings'].append(f"Column '{col}' has {null_pct:.2%} null values")
        
        result['stats']['null_analysis'] = null_analysis
        
        # Duplicate detection
        duplicate_count = df.duplicated().sum()
        duplicate_pct = duplicate_count / len(df)
        result['stats']['duplicate_count'] = duplicate_count
        result['stats']['duplicate_percentage'] = round(duplicate_pct, 4)
        
        if duplicate_pct > 0.1:
            result['warnings'].append(f"Found {duplicate_count} duplicate rows ({duplicate_pct:.2%})")
        
        # Column validation
        for col in df.columns:
            if df[col].nunique() == 1:
                result['warnings'].append(f"Column '{col}' has only one unique value")
        
        # Set validation status
        if result['errors']:
            result['is_valid'] = False
```

Create `csv_validator/function.json`:
```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "authLevel": "function",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": [
        "post"
      ]
    },
    {
      "type": "http",
      "direction": "out",
      "name": "$return"
    }
  ]
}
```

### 4.3 Deploy Function App
```bash
# Deploy function app
func azure functionapp publish $FUNCTION_APP --python

# Get function URL
FUNCTION_URL=$(az functionapp function show \
    --resource-group $RESOURCE_GROUP \
    --name $FUNCTION_APP \
    --function-name csv_validator \
    --query invokeUrlTemplate -o tsv)

echo "Function URL: $FUNCTION_URL"
```

## 📊 Step 5: Create Data Factory Pipeline

### 5.1 Create Linked Services
```bash
# Create Azure Function linked service
az datafactory linked-service create \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --name "AzureFunction_LinkedService" \
    --properties '{
        "type": "AzureFunction",
        "typeProperties": {
            "functionAppUrl": "https://'$FUNCTION_APP'.azurewebsites.net",
            "authentication": "MSI"
        }
    }'

# Create Storage linked service
az datafactory linked-service create \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --name "AzureDataLakeStorage_LinkedService" \
    --properties '{
        "type": "AzureBlobFS",
        "typeProperties": {
            "url": "https://'$STORAGE_ACCOUNT'.dfs.core.windows.net/"
        }
    }'
```

### 5.2 Create Dataset
```bash
# Create CSV dataset
az datafactory dataset create \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --name "CSV_Dataset" \
    --properties '{
        "type": "DelimitedText",
        "linkedServiceName": {
            "referenceName": "AzureDataLakeStorage_LinkedService",
            "type": "LinkedServiceReference"
        },
        "parameters": {
            "container": {
                "type": "string",
                "defaultValue": "raw-data"
            },
            "fileName": {
                "type": "string"
            }
        },
        "typeProperties": {
            "location": {
                "type": "AzureBlobFSLocation",
                "fileName": {
                    "value": "@dataset().fileName",
                    "type": "Expression"
                },
                "fileSystem": {
                    "value": "@dataset().container",
                    "type": "Expression"
                }
            },
            "columnDelimiter": ",",
            "escapeChar": "\\",
            "firstRowAsHeader": true,
            "quoteChar": "\""
        }
    }'
```

### 5.3 Create Pipeline
Create `pipeline.json`:
```json
{
    "name": "CSV_Validation_Pipeline",
    "properties": {
        "activities": [
            {
                "name": "Pre_Validation_Function",
                "type": "AzureFunctionActivity",
                "dependsOn": [],
                "policy": {
                    "timeout": "00:10:00",
                    "retry": 2,
                    "retryIntervalInSeconds": 30
                },
                "userProperties": [],
                "typeProperties": {
                    "functionName": "csv_validator",
                    "method": "POST",
                    "body": {
                        "container_name": "@pipeline().parameters.container_name",
                        "blob_name": "@pipeline().parameters.blob_name"
                    }
                },
                "linkedServiceName": {
                    "referenceName": "AzureFunction_LinkedService",
                    "type": "LinkedServiceReference"
                }
            },
            {
                "name": "Validation_Check",
                "type": "IfCondition",
                "dependsOn": [
                    {
                        "activity": "Pre_Validation_Function",
                        "dependencyConditions": ["Succeeded"]
                    }
                ],
                "userProperties": [],
                "typeProperties": {
                    "expression": {
                        "value": "@activity('Pre_Validation_Function').output.is_valid",
                        "type": "Expression"
                    },
                    "ifTrueActivities": [
                        {
                            "name": "ADF_Basic_Validation",
                            "type": "Validation",
                            "dependsOn": [],
                            "userProperties": [],
                            "typeProperties": {
                                "dataset": {
                                    "referenceName": "CSV_Dataset",
                                    "type": "DatasetReference",
                                    "parameters": {
                                        "container": "@pipeline().parameters.container_name",
                                        "fileName": "@pipeline().parameters.blob_name"
                                    }
                                },
                                "timeout": "00:05:00",
                                "sleep": 10,
                                "minimumSize": 1
                            }
                        },
                        {
                            "name": "Get_Metadata",
                            "type": "GetMetadata",
                            "dependsOn": [
                                {
                                    "activity": "ADF_Basic_Validation",
                                    "dependencyConditions": ["Succeeded"]
                                }
                            ],
                            "userProperties": [],
                            "typeProperties": {
                                "dataset": {
                                    "referenceName": "CSV_Dataset",
                                    "type": "DatasetReference",
                                    "parameters": {
                                        "container": "@pipeline().parameters.container_name",
                                        "fileName": "@pipeline().parameters.blob_name"
                                    }
                                },
                                "fieldList": [
                                    "columnCount",
                                    "columnNames",
                                    "size",
                                    "lastModified",
                                    "itemName"
                                ]
                            }
                        },
                        {
                            "name": "Copy_To_Validated",
                            "type": "Copy",
                            "dependsOn": [
                                {
                                    "activity": "Get_Metadata",
                                    "dependencyConditions": ["Succeeded"]
                                }
                            ],
                            "policy": {
                                "timeout": "00:30:00",
                                "retry": 1,
                                "retryIntervalInSeconds": 30
                            },
                            "userProperties": [],
                            "typeProperties": {
                                "source": {
                                    "type": "DelimitedTextSource",
                                    "storeSettings": {
                                        "type": "AzureBlobFSReadSettings",
                                        "recursive": false,
                                        "enablePartitionDiscovery": false
                                    },
                                    "formatSettings": {
                                        "type": "DelimitedTextReadSettings"
                                    }
                                },
                                "sink": {
                                    "type": "DelimitedTextSink",
                                    "storeSettings": {
                                        "type": "AzureBlobFSWriteSettings"
                                    },
                                    "formatSettings": {
                                        "type": "DelimitedTextWriteSettings",
                                        "quoteAllText": false,
                                        "fileExtension": ".csv"
                                    }
                                }
                            },
                            "inputs": [
                                {
                                    "referenceName": "CSV_Dataset",
                                    "type": "DatasetReference",
                                    "parameters": {
                                        "container": "@pipeline().parameters.container_name",
                                        "fileName": "@pipeline().parameters.blob_name"
                                    }
                                }
                            ],
                            "outputs": [
                                {
                                    "referenceName": "CSV_Dataset",
                                    "type": "DatasetReference",
                                    "parameters": {
                                        "container": "validated-data",
                                        "fileName": "@pipeline().parameters.blob_name"
                                    }
                                }
                            ]
                        }
                    ],
                    "ifFalseActivities": [
                        {
                            "name": "Copy_To_Error",
                            "type": "Copy",
                            "dependsOn": [],
                            "policy": {
                                "timeout": "00:30:00",
                                "retry": 1,
                                "retryIntervalInSeconds": 30
                            },
                            "userProperties": [],
                            "typeProperties": {
                                "source": {
                                    "type": "DelimitedTextSource",
                                    "storeSettings": {
                                        "type": "AzureBlobFSReadSettings",
                                        "recursive": false,
                                        "enablePartitionDiscovery": false
                                    },
                                    "formatSettings": {
                                        "type": "DelimitedTextReadSettings"
                                    }
                                },
                                "sink": {
                                    "type": "DelimitedTextSink",
                                    "storeSettings": {
                                        "type": "AzureBlobFSWriteSettings"
                                    },
                                    "formatSettings": {
                                        "type": "DelimitedTextWriteSettings",
                                        "quoteAllText": false,
                                        "fileExtension": ".csv"
                                    }
                                }
                            },
                            "inputs": [
                                {
                                    "referenceName": "CSV_Dataset",
                                    "type": "DatasetReference",
                                    "parameters": {
                                        "container": "@pipeline().parameters.container_name",
                                        "fileName": "@pipeline().parameters.blob_name"
                                    }
                                }
                            ],
                            "outputs": [
                                {
                                    "referenceName": "CSV_Dataset",
                                    "type": "DatasetReference",
                                    "parameters": {
                                        "container": "error-data",
                                        "fileName": "@pipeline().parameters.blob_name"
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        ],
        "parameters": {
            "container_name": {
                "type": "string",
                "defaultValue": "raw-data"
            },
            "blob_name": {
                "type": "string"
            }
        }
    }
}
```

Deploy the pipeline:
```bash
az datafactory pipeline create \
    --resource-group $RESOURCE_GROUP \
    --factory-name $DATA_FACTORY \
    --name "CSV_Validation_Pipeline" \
    --pipeline @pipeline.json
```

## 🔍 Step 6: Configure Monitoring and Alerts

### 6.1 Create Alert Rules
```bash
# Get Application Insights resource ID
APP_INSIGHTS_ID=$(az monitor app-insights component show \
    --app $(az deployment group show \
        --resource-group $RESOURCE_GROUP \
        --name infrastructure \
        --query properties.outputs.appInsightsName.value -o tsv) \
    --resource-group $RESOURCE_GROUP \
    --query id -o tsv)

# Create alert rule for validation failures
az monitor metrics alert create \
    --name "CSV_Validation_Failure_Alert" \
    --resource-group $RESOURCE_GROUP \
    --scopes $APP_INSIGHTS_ID \
    --condition "count 'customDimensions/validation_status' includes 'FAIL' > 0" \
    --description "Alert when CSV validation fails" \
    --evaluation-frequency 5m \
    --window-size 5m \
    --severity 2
```

### 6.2 Create Action Group
```bash
# Create action group for notifications
az monitor action-group create \
    --name "CSV_Validation_Actions" \
    --resource-group $RESOURCE_GROUP \
    --short-name "CSVVal" \
    --action email "admin" "your-email@company.com"
```

## 🧪 Step 7: Testing the Solution

### 7.1 Create Test Data