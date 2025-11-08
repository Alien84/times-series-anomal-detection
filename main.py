"""
ML Monitoring System - Core Logic Demo
Demonstrates anomaly detection and root cause analysis without AWS dependencies
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# STEP 1: GENERATE DUMMY DATA
# ============================================================================

def generate_time_series_data(n_points=1000, n_metrics=20):
    """
    Generate dummy time series data simulating system metrics
    Args:
        n_points: Number of time points (e.g., 1000 = ~10 days at 15-min intervals)
        n_metrics: Number of metrics to monitor
    """
    print("Generating time series data...")
    
    # Create timestamps (15-minute intervals)
    start_time = datetime.now() - timedelta(days=10)
    timestamps = [start_time + timedelta(minutes=15*i) for i in range(n_points)]
    
    # Generate normal behavior with patterns
    data = {}
    data['timestamp'] = timestamps
    
    for i in range(n_metrics):
        # Base pattern with daily seasonality
        base = 50 + 20 * np.sin(2 * np.pi * np.arange(n_points) / 96)  # 96 = 24 hours
        
        # Add weekly pattern
        weekly = 10 * np.sin(2 * np.pi * np.arange(n_points) / (96 * 7))
        
        # Add noise
        noise = np.random.normal(0, 5, n_points)
        
        # Combine
        metric_values = base + weekly + noise
        
        # Make all values positive
        metric_values = np.abs(metric_values)
        
        data[f'metric_{i}'] = metric_values
    
    df = pd.DataFrame(data)
    
    # INJECT ANOMALIES
    # Anomaly 1: Spike at point 500 (CPU spike scenario)
    df.loc[500:510, 'metric_0'] = df.loc[500:510, 'metric_0'] * 3
    df.loc[500:510, 'metric_1'] = df.loc[500:510, 'metric_1'] * 2.5
    
    # Anomaly 2: Drop at point 750 (Service degradation)
    df.loc[750:760, 'metric_5'] = df.loc[750:760, 'metric_5'] * 0.3
    df.loc[750:760, 'metric_6'] = df.loc[750:760, 'metric_6'] * 0.2
    
    # Anomaly 3: Gradual increase at point 900 (Memory leak)
    df.loc[900:950, 'metric_10'] = df.loc[900:950, 'metric_10'] * np.linspace(1, 2.5, 51)
    
    return df


def generate_equipment_alerts(timestamps):
    """Generate dummy equipment alerts"""
    print("Generating equipment alerts...")
    
    alerts = []
    
    # Alert 1: Corresponds to anomaly 1 (around timestamp 500)
    alerts.append({
        'timestamp': timestamps[502],
        'equipment_id': 'SERVER_A1',
        'alert_type': 'HIGH_LOAD',
        'severity': 'CRITICAL',
        'message': 'CPU threshold exceeded'
    })
    
    # Alert 2: Corresponds to anomaly 2 (around timestamp 750)
    alerts.append({
        'timestamp': timestamps[751],
        'equipment_id': 'DATABASE_B2',
        'alert_type': 'CONNECTION_TIMEOUT',
        'severity': 'HIGH',
        'message': 'Database connection pool exhausted'
    })
    
    # Alert 3: Corresponds to anomaly 3 (around timestamp 900)
    alerts.append({
        'timestamp': timestamps[905],
        'equipment_id': 'APP_SERVER_C3',
        'alert_type': 'MEMORY_WARNING',
        'severity': 'MEDIUM',
        'message': 'Memory usage increasing'
    })
    
    # Some noise alerts (false positives)
    alerts.append({
        'timestamp': timestamps[300],
        'equipment_id': 'NETWORK_D4',
        'alert_type': 'PACKET_LOSS',
        'severity': 'LOW',
        'message': 'Minor packet loss detected'
    })
    
    return pd.DataFrame(alerts)


def generate_change_records(timestamps):
    """Generate dummy change records (deployments, configs, etc.)"""
    print("Generating change records...")
    
    changes = []
    
    # Change 1: Deployment just before anomaly 1
    changes.append({
        'timestamp': timestamps[498],
        'change_type': 'DEPLOYMENT',
        'system': 'API_SERVICE',
        'description': 'Deployed version 2.3.1',
        'change_by': 'DevOps Team'
    })
    
    # Change 2: Config change before anomaly 2
    changes.append({
        'timestamp': timestamps[748],
        'change_type': 'CONFIG_CHANGE',
        'system': 'DATABASE_B2',
        'description': 'Updated connection pool settings',
        'change_by': 'DBA Team'
    })
    
    # Change 3: No change before anomaly 3 (organic issue)
    
    # Normal changes (no issues)
    changes.append({
        'timestamp': timestamps[200],
        'change_type': 'DEPLOYMENT',
        'system': 'WEB_FRONTEND',
        'description': 'UI update',
        'change_by': 'Frontend Team'
    })
    
    return pd.DataFrame(changes)


def generate_customer_service_data(timestamps):
    """Generate dummy customer service impact data"""
    print("Generating customer service data...")
    
    service_data = []
    
    # Normal service levels most of the time
    for i in range(0, len(timestamps), 50):  # Sample every 50 points
        service_data.append({
            'timestamp': timestamps[i],
            'region': 'LONDON',
            'service_level': np.random.uniform(98, 100),  # Normal: 98-100%
            'customer_complaints': np.random.randint(0, 5)
        })
        service_data.append({
            'timestamp': timestamps[i],
            'region': 'MANCHESTER',
            'service_level': np.random.uniform(98, 100),
            'customer_complaints': np.random.randint(0, 5)
        })
    
    # Impact during anomaly 1
    service_data.append({
        'timestamp': timestamps[505],
        'region': 'LONDON',
        'service_level': 85.5,  # Degraded
        'customer_complaints': 45
    })
    
    # Impact during anomaly 2
    service_data.append({
        'timestamp': timestamps[755],
        'region': 'MANCHESTER',
        'service_level': 78.2,  # Severely degraded
        'customer_complaints': 78
    })
    
    return pd.DataFrame(service_data)


# ============================================================================
# STEP 2: ANOMALY DETECTION
# ============================================================================

class AnomalyDetector:
    """Simple anomaly detection using multiple methods"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.isolation_forest = IsolationForest(contamination=0.05, random_state=42)
        
    def detect_statistical_anomalies(self, df, column, window=96):
        """
        Simple statistical anomaly detection using rolling statistics
        window=96 means 1 day (96 * 15 minutes)
        """
        rolling_mean = df[column].rolling(window=window, center=True).mean()
        rolling_std = df[column].rolling(window=window, center=True).std()
        
        # Calculate z-score
        z_scores = np.abs((df[column] - rolling_mean) / rolling_std)
        
        # Mark as anomaly if z-score > 3 (99.7% confidence)
        anomalies = z_scores > 3
        
        return anomalies, z_scores
    
    def detect_ml_anomalies(self, df, metric_columns):
        """
        ML-based anomaly detection using Isolation Forest
        Looks at multiple metrics together
        """
        # Prepare data
        X = df[metric_columns].values
        X_scaled = self.scaler.fit_transform(X)
        
        # Predict anomalies (-1 = anomaly, 1 = normal)
        predictions = self.isolation_forest.fit_predict(X_scaled)
        
        # Get anomaly scores
        scores = self.isolation_forest.score_samples(X_scaled)
        
        return predictions == -1, scores
    
    def detect_all_anomalies(self, df):
        """Run all anomaly detection methods"""
        print("\nDetecting anomalies...")
        
        metric_columns = [col for col in df.columns if col.startswith('metric_')]
        
        results = pd.DataFrame()
        results['timestamp'] = df['timestamp']
        
        # Method 1: Statistical detection on key metrics
        stat_anomalies = []
        for col in metric_columns[:10]:  # Check first 10 metrics
            anomalies, z_scores = self.detect_statistical_anomalies(df, col)
            stat_anomalies.append(anomalies)
        
        # Combine: anomaly if any metric is anomalous
        results['statistical_anomaly'] = pd.DataFrame(stat_anomalies).T.any(axis=1)
        
        # Method 2: ML-based multivariate detection
        ml_anomalies, ml_scores = self.detect_ml_anomalies(df, metric_columns)
        results['ml_anomaly'] = ml_anomalies
        results['anomaly_score'] = ml_scores
        
        # Combined decision: Both methods agree = high confidence
        results['is_anomaly'] = results['statistical_anomaly'] | results['ml_anomaly']
        results['confidence'] = 'LOW'
        results.loc[results['statistical_anomaly'] & results['ml_anomaly'], 'confidence'] = 'HIGH'
        results.loc[results['is_anomaly'] & (results['confidence'] == 'LOW'), 'confidence'] = 'MEDIUM'
        
        # Add affected metrics
        results['affected_metrics'] = ''
        for idx, row in results[results['is_anomaly']].iterrows():
            affected = []
            for col in metric_columns[:10]:
                if df.loc[idx, col] > df[col].mean() + 2 * df[col].std() or \
                   df.loc[idx, col] < df[col].mean() - 2 * df[col].std():
                    affected.append(col)
            results.at[idx, 'affected_metrics'] = ', '.join(affected[:3])  # Top 3
        
        anomaly_count = results['is_anomaly'].sum()
        print(f"Found {anomaly_count} anomalies")
        print(f"  High confidence: {(results['confidence'] == 'HIGH').sum()}")
        print(f"  Medium confidence: {(results['confidence'] == 'MEDIUM').sum()}")
        print(f"  Low confidence: {(results['confidence'] == 'LOW').sum()}")
        
        return results


# ============================================================================
# STEP 3: ROOT CAUSE ANALYSIS
# ============================================================================

class RootCauseAnalyzer:
    """Correlate anomalies with alerts, changes, and customer impact"""
    
    def __init__(self, time_window_minutes=30):
        self.time_window = timedelta(minutes=time_window_minutes)
        
    def find_temporal_correlations(self, anomaly_time, events_df, event_type):
        """
        Find events that occurred near the anomaly time
        """
        correlated = []
        
        for idx, event in events_df.iterrows():
            event_time = event['timestamp']
            time_diff = abs((event_time - anomaly_time).total_seconds() / 60)  # minutes
            
            if time_diff <= self.time_window.total_seconds() / 60:
                correlated.append({
                    'event_type': event_type,
                    'time_diff_minutes': time_diff,
                    'event_data': event.to_dict()
                })
        
        return correlated
    
    def calculate_correlation_score(self, correlations):
        """
        Score how likely the correlated events are the root cause
        Based on: timing, event type, severity
        """
        if not correlations:
            return 0.0
        
        scores = []
        for corr in correlations:
            # Closer in time = higher score
            time_score = max(0, 1 - (corr['time_diff_minutes'] / 30))
            
            # Weight by event type
            type_weights = {
                'DEPLOYMENT': 0.9,
                'CONFIG_CHANGE': 0.8,
                'CRITICAL': 0.85,
                'HIGH': 0.7,
                'MEDIUM': 0.5
            }
            
            event_data = corr['event_data']
            type_score = 0.5  # default
            
            if corr['event_type'] == 'change':
                type_score = type_weights.get(event_data.get('change_type'), 0.5)
            elif corr['event_type'] == 'alert':
                type_score = type_weights.get(event_data.get('severity'), 0.5)
            
            scores.append(time_score * type_score)
        
        return max(scores) if scores else 0.0
    
    def analyze_incident(self, anomaly_row, alerts_df, changes_df, service_df):
        """
        Perform root cause analysis for a single anomaly
        """
        anomaly_time = anomaly_row['timestamp']
        
        # Find correlated events
        alert_correlations = self.find_temporal_correlations(
            anomaly_time, alerts_df, 'alert'
        )
        change_correlations = self.find_temporal_correlations(
            anomaly_time, changes_df, 'change'
        )
        service_correlations = self.find_temporal_correlations(
            anomaly_time, service_df, 'service_impact'
        )
        
        # Calculate correlation scores
        alert_score = self.calculate_correlation_score(alert_correlations)
        change_score = self.calculate_correlation_score(change_correlations)
        
        # Determine most likely root cause
        all_correlations = alert_correlations + change_correlations
        
        if not all_correlations:
            root_cause = "UNKNOWN - No correlated events found"
            confidence = "LOW"
        elif change_score > alert_score:
            change_event = change_correlations[0]['event_data']
            root_cause = f"Likely caused by {change_event['change_type']}: {change_event['description']}"
            confidence = "HIGH" if change_score > 0.7 else "MEDIUM"
        else:
            alert_event = alert_correlations[0]['event_data']
            root_cause = f"Related to {alert_event['alert_type']} on {alert_event['equipment_id']}"
            confidence = "MEDIUM" if alert_score > 0.6 else "LOW"
        
        # Check customer impact
        customer_impact = "NONE"
        if service_correlations:
            service_event = service_correlations[0]['event_data']
            if service_event.get('service_level', 100) < 95:
                customer_impact = f"HIGH - {service_event['region']} affected"
            elif service_event.get('customer_complaints', 0) > 10:
                customer_impact = f"MEDIUM - Increased complaints in {service_event['region']}"
        
        return {
            'timestamp': anomaly_time,
            'affected_metrics': anomaly_row.get('affected_metrics', 'N/A'),
            'root_cause': root_cause,
            'confidence': confidence,
            'customer_impact': customer_impact,
            'correlated_alerts': len(alert_correlations),
            'correlated_changes': len(change_correlations),
            'alert_details': alert_correlations,
            'change_details': change_correlations
        }
    
    def analyze_all_anomalies(self, anomalies_df, alerts_df, changes_df, service_df):
        """
        Analyze all detected anomalies
        """
        print("\nPerforming root cause analysis...")
        
        incidents = []
        anomaly_rows = anomalies_df[anomalies_df['is_anomaly']].copy()
        
        for idx, anomaly in anomaly_rows.iterrows():
            incident = self.analyze_incident(anomaly, alerts_df, changes_df, service_df)
            incidents.append(incident)
        
        incidents_df = pd.DataFrame(incidents)
        print(f"Analyzed {len(incidents)} incidents")
        
        return incidents_df


# ============================================================================
# STEP 4: RECOMMENDATION ENGINE
# ============================================================================

class RecommendationEngine:
    """Generate action recommendations based on root cause analysis"""
    
    def __init__(self):
        # Simple rule-based recommendations (in real system, this would be ML-based)
        self.recommendation_rules = {
            'DEPLOYMENT': {
                'action': 'ROLLBACK',
                'description': 'Rollback recent deployment',
                'auto_remediate': False  # Requires approval
            },
            'CONFIG_CHANGE': {
                'action': 'REVERT_CONFIG',
                'description': 'Revert configuration changes',
                'auto_remediate': False
            },
            'HIGH_LOAD': {
                'action': 'SCALE_UP',
                'description': 'Scale up resources',
                'auto_remediate': True  # Can auto-scale
            },
            'MEMORY_WARNING': {
                'action': 'RESTART_SERVICE',
                'description': 'Restart affected service to clear memory',
                'auto_remediate': True
            },
            'CONNECTION_TIMEOUT': {
                'action': 'INCREASE_POOL',
                'description': 'Increase connection pool size',
                'auto_remediate': False
            },
            'UNKNOWN': {
                'action': 'MANUAL_INVESTIGATION',
                'description': 'Requires manual investigation',
                'auto_remediate': False
            }
        }
    
    def generate_recommendation(self, incident):
        """Generate action recommendation for an incident"""
        
        root_cause = incident['root_cause']
        confidence = incident['confidence']
        customer_impact = incident['customer_impact']
        
        # Extract key terms from root cause
        recommendation = None
        for key in self.recommendation_rules.keys():
            if key in root_cause:
                recommendation = self.recommendation_rules[key].copy()
                break
        
        if not recommendation:
            recommendation = self.recommendation_rules['UNKNOWN'].copy()
        
        # Adjust based on confidence and impact
        if confidence == 'LOW':
            recommendation['auto_remediate'] = False
            recommendation['action_type'] = 'LOG_AND_MONITOR'
        elif confidence == 'MEDIUM':
            recommendation['action_type'] = 'ALERT_ENGINEER'
        elif confidence == 'HIGH' and recommendation['auto_remediate']:
            recommendation['action_type'] = 'AUTO_REMEDIATE'
        else:
            recommendation['action_type'] = 'ALERT_WITH_SUGGESTION'
        
        # Increase priority if customer impact is high
        if 'HIGH' in customer_impact:
            recommendation['priority'] = 'P1_CRITICAL'
        elif 'MEDIUM' in customer_impact:
            recommendation['priority'] = 'P2_HIGH'
        else:
            recommendation['priority'] = 'P3_NORMAL'
        
        recommendation['incident'] = incident
        
        return recommendation
    
    def generate_all_recommendations(self, incidents_df):
        """Generate recommendations for all incidents"""
        print("\nGenerating recommendations...")
        
        recommendations = []
        for idx, incident in incidents_df.iterrows():
            rec = self.generate_recommendation(incident)
            recommendations.append(rec)
        
        # Group by action type
        action_summary = defaultdict(int)
        for rec in recommendations:
            action_summary[rec['action_type']] += 1
        
        print(f"Generated {len(recommendations)} recommendations:")
        for action_type, count in action_summary.items():
            print(f"  {action_type}: {count}")
        
        return recommendations


# ============================================================================
# STEP 5: MAIN EXECUTION & REPORTING
# ============================================================================

def print_incident_report(recommendations):
    """Print a human-readable incident report"""
    print("\n" + "="*80)
    print("INCIDENT REPORT")
    print("="*80)
    
    for i, rec in enumerate(recommendations, 1):
        incident = rec['incident']
        
        print(f"\n--- INCIDENT #{i} ---")
        print(f"Time: {incident['timestamp']}")
        print(f"Affected Metrics: {incident['affected_metrics']}")
        print(f"Root Cause: {incident['root_cause']}")
        print(f"Confidence: {incident['confidence']}")
        print(f"Customer Impact: {incident['customer_impact']}")
        print(f"\nRECOMMENDATION:")
        print(f"  Priority: {rec['priority']}")
        print(f"  Action: {rec['action']} - {rec['description']}")
        print(f"  Action Type: {rec['action_type']}")
        
        # Show correlated events
        if incident['correlated_changes'] > 0:
            print(f"\n  Correlated Changes:")
            for change in incident['change_details']:
                change_data = change['event_data']
                print(f"    - {change_data['change_type']}: {change_data['description']}")
                print(f"      ({change['time_diff_minutes']:.1f} min before anomaly)")
        
        if incident['correlated_alerts'] > 0:
            print(f"\n  Correlated Alerts:")
            for alert in incident['alert_details']:
                alert_data = alert['event_data']
                print(f"    - {alert_data['alert_type']} on {alert_data['equipment_id']}")
                print(f"      ({alert['time_diff_minutes']:.1f} min from anomaly)")
        
        print("-" * 80)


def main():
    """Main execution flow"""
    
    print("="*80)
    print("ML MONITORING SYSTEM - DEMO")
    print("="*80)
    
    # Step 1: Generate all data sources
    print("\n[STEP 1] Generating dummy data...")
    ts_data = generate_time_series_data(n_points=1000, n_metrics=20)
    alerts_data = generate_equipment_alerts(ts_data['timestamp'])
    changes_data = generate_change_records(ts_data['timestamp'])
    service_data = generate_customer_service_data(ts_data['timestamp'])
    
    print(f"Generated {len(ts_data)} time series points")
    print(f"Generated {len(alerts_data)} equipment alerts")
    print(f"Generated {len(changes_data)} change records")
    print(f"Generated {len(service_data)} service data points")
    
    # Step 2: Detect anomalies
    print("\n[STEP 2] Detecting anomalies...")
    detector = AnomalyDetector()
    anomalies = detector.detect_all_anomalies(ts_data)
    
    # Step 3: Root cause analysis
    print("\n[STEP 3] Analyzing root causes...")
    rca = RootCauseAnalyzer(time_window_minutes=30)
    incidents = rca.analyze_all_anomalies(
        anomalies, alerts_data, changes_data, service_data
    )
    
    # Step 4: Generate recommendations
    print("\n[STEP 4] Generating recommendations...")
    rec_engine = RecommendationEngine()
    recommendations = rec_engine.generate_all_recommendations(incidents)
    
    # Step 5: Print report
    print_incident_report(recommendations)
    
    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total time points analyzed: {len(ts_data)}")
    print(f"Anomalies detected: {anomalies['is_anomaly'].sum()}")
    print(f"High confidence incidents: {len([r for r in recommendations if r['incident']['confidence'] == 'HIGH'])}")
    print(f"Auto-remediable incidents: {len([r for r in recommendations if r['auto_remediate']])}")
    print(f"Incidents with customer impact: {len([r for r in recommendations if 'NONE' not in r['incident']['customer_impact']])}")
    print("="*80)


if __name__ == "__main__":
    main()