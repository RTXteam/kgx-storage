pipeline {
    options {
        timestamps()
        skipDefaultCheckout()
        disableConcurrentBuilds()
    }
    agent {
        node { label 'translator && build && aws' }
    }
    parameters {
        string(name: 'BUILD_VERSION', defaultValue: '', description: 'The build version to deploy (optional)')
        string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'AWS Region to deploy')
        string(name: 'EKS_CLUSTER', defaultValue: 'translator-eks-ci-blue-cluster', description: 'EKS Cluster name')
        booleanParam(name: 'SKIP_TESTS', defaultValue: false, description: 'Skip health check tests')
    }
    triggers {
        pollSCM('H/5 * * * *')
    }
    environment {
        AWS_ACCOUNT_ID = "853771734544"
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"
        ECR_REPOSITORY = "kgx-storage"
        IMAGE_NAME = "${ECR_REGISTRY}/${ECR_REPOSITORY}"
        KUBERNETES_BLUE_CLUSTER_NAME = "${params.EKS_CLUSTER}"
        DEPLOY_ENV = "ci"
        NAMESPACE = 'kgx-storage'
        S3_BUCKET = 'kgx-translator-ingests'
    }
    stages {
        stage('Build Version'){
            when { expression { return !params.BUILD_VERSION } }
            steps{
                script {
                    BUILD_VERSION_GENERATED = VersionNumber(
                        versionNumberString: 'v${BUILD_YEAR, XX}.${BUILD_MONTH, XX}${BUILD_DAY, XX}.${BUILDS_TODAY}',
                        projectStartDate:    '1970-01-01',
                        skipFailedBuilds:    true)
                    currentBuild.displayName = BUILD_VERSION_GENERATED
                    env.BUILD_VERSION = BUILD_VERSION_GENERATED
                    env.BUILD = 'true'
                }
            }
        }
        stage('Checkout source code') {
            steps {
                cleanWs()
                checkout scm
            }
        }
        stage('Build Docker') {
           when { expression { return env.BUILD == 'true' }}
            steps {
                script {
                    sh """#!/bin/bash
                    set -e
                    
                    echo "Building Docker image for kgx-storage..."
                    docker build -t ${ECR_REPOSITORY}:${BUILD_VERSION} .
                    docker tag ${ECR_REPOSITORY}:${BUILD_VERSION} ${IMAGE_NAME}:${BUILD_VERSION}
                    docker tag ${ECR_REPOSITORY}:${BUILD_VERSION} ${IMAGE_NAME}:latest
                    
                    echo "Logging into ECR..."
                    aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}
                    
                    echo "Pushing images to ECR..."
                    docker push ${IMAGE_NAME}:${BUILD_VERSION}
                    docker push ${IMAGE_NAME}:latest
                    
                    echo "Image pushed successfully: ${IMAGE_NAME}:${BUILD_VERSION}"
                    """
                }
            }
        }
        stage('Deploy to AWS EKS Blue') {
            agent {
                label 'translator && ci && deploy'
            }
            steps {
                script {
                    configFileProvider([
                        configFile(fileId: 'values-kgx-storage-ci.yaml', targetLocation: 'values-ncats.yaml'),
                        configFile(fileId: 'prepare.sh', targetLocation: 'prepare.sh')
                    ]){
                        sh '''
                        aws --region ${AWS_REGION} eks update-kubeconfig --name ${KUBERNETES_BLUE_CLUSTER_NAME}
                        /bin/bash prepare.sh
                        cp values-ncats.yaml translator-ops/ops/kgx-storage/
                        cd translator-ops/ops/kgx-storage/
                        /bin/bash deploy.sh
                        '''
                    }
                }
            }
            post {
                always {
                    echo "Clean up the workspace in deploy node!"
                    cleanWs()
                }
            }
        }
    }
    post {
        success {
            echo "Pipeline completed successfully!"
            echo "Image: ${IMAGE_NAME}:${BUILD_VERSION}"
        }
        failure {
            echo "Pipeline failed!"
        }
    }
}