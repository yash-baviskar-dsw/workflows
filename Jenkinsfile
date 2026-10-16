
pipeline {
    agent any

    options {
        timestamps()
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm

                sh '''
                    echo "Repository: $(git remote get-url origin)"
                    echo "Branch: $(git branch --show-current)"
                    echo "Commit: $(git rev-parse HEAD)"
                '''
            }
        }

        stage('Test service1') {
            steps {
                dir('service1') {
                    sh '''
                        set -eu

                        python3 -m venv .venv
                        . .venv/bin/activate

                        python3 -m pip install --upgrade pip
                        python3 -m pip install -r requirements.txt
                        python3 -m pip install pytest

                        python3 -m pytest
                    '''
                }
            }
        }

        stage('Test service2') {
            steps {
                dir('service2') {
                    sh '''
                        set -eu

                        python3 -m venv .venv
                        . .venv/bin/activate

                        python3 -m pip install --upgrade pip
                        python3 -m pip install -r requirements.txt

                        python3 -c \
                          "from app import app; print('service2 OK')"
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'CI PASSED: all service checks succeeded.'
        }

        failure {
            echo 'CI FAILED: inspect the failed stage and console log.'
        }

        always {
            echo "Build result: ${currentBuild.currentResult}"
        }
    }
}

