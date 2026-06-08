# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.1
#   kernelspec:
#     display_name: PySpark
#     language: python
#     name: pysparkkernel
# ---

# %% [markdown]
# # 0. Setup

# %%
# Useful imports
from functools import reduce
from pyspark.sql.functions import lit
from pyspark.sql import SparkSession
from pyspark.sql.functions import to_timestamp
from pyspark.sql.functions import unix_timestamp

from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.sql.functions import hour, dayofweek, when, col, count

from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.classification import LogisticRegression

# %%
print(f'Start Spark name:{spark._sc.appName}, version:{spark.version}')

# %%
# %%configure -f
{ "conf": {
        "mapreduce.input.fileinputformat.input.dir.recursive": true,
        "spark.sql.extensions": "com.hortonworks.spark.sql.rule.Extensions",
        "spark.kryo.registrator": "com.qubole.spark.hiveacid.util.HiveAcidKyroRegistrator",
        "spark.sql.hive.hiveserver2.jdbc.url": "jdbc:hive2://iccluster065.iccluster.epfl.ch:2181,iccluster080.iccluster.epfl.ch:2181,iccluster066.iccluster.epfl.ch:2181/;serviceDiscoveryMode=zooKeeper;zooKeeperNamespace=hiveserver2",
        "spark.datasource.hive.warehouse.read.mode": "JDBC_CLUSTER",
        "spark.driver.extraClassPath": "/opt/cloudera/parcels/SPARK3/lib/hwc_for_spark3/hive-warehouse-connector-spark3-assembly-1.0.0.3.3.7190.2-1.jar",
        "spark.executor.extraClassPath": "/opt/cloudera/parcels/SPARK3/lib/hwc_for_spark3/hive-warehouse-connector-spark3-assembly-1.0.0.3.3.7190.2-1.jar"
    }
}

# %%
import os
print(f"remote USER={os.getenv('USER',None)}")

# %%
# %%local
import os
print(f"local USER={os.getenv('USER',None)}")

# %%
# %%local
import os
username=os.getenv('USER', 'anonymous')
hadoop_fs=os.getenv('HADOOP_DEFAULT_FS', 'hdfs://iccluster067.iccluster.epfl.ch:8020')
print(f"local username={username}\nhadoop_fs={hadoop_fs}")

 # %%
 # (prevent deprecated np.bool error since numpy 1.24, until a new version of pandas/Spark fixes this)
import numpy as np
np.bool = np.bool_

username=spark.conf.get('spark.executorEnv.USERNAME', 'anonymous')
hadoop_fs=spark.conf.get('spark.executorEnv.HADOOP_DEFAULT_FS','hdfs://iccluster067.iccluster.epfl.ch:8020')
print(f"remote username={username}\nhadoop_fs={hadoop_fs}")

# %% [markdown]
# # 1. Model creation

# %% [markdown]
# ### a) Data sanitizing

# %%
from pyspark.sql.functions import col

stations_df = spark.read.csv('/data/wunderground/csv/stations', header=True)
trips_df = spark.read.orc('/data/sbb/orc/istdaten')

# Renaming columns with English translations
trips_df = (trips_df
            .withColumnRenamed("betriebstag", "operation_day")
            .withColumnRenamed("fahrt_bezeichner", "trip_identifier")
            .withColumnRenamed("betreiber_id", "operator_id")
            .withColumnRenamed("betreiber_abk", "operator_abbreviation")
            .withColumnRenamed("betreiber_name", "operator_name")
            .withColumnRenamed("produkt_id", "product_id")
            .withColumnRenamed("linien_id", "line_id")
            .withColumnRenamed("linien_text", "line_text")
            .withColumnRenamed("umlauf_id", "rotation_id")
            .withColumnRenamed("verkehrsmittel_text", "transportation_text")
            .withColumnRenamed("zusatzfahrt_tf", "additional_trip_tf")
            .withColumnRenamed("faellt_aus_tf", "is_cancelled_tf")
            .withColumnRenamed("bpuic", "station_code")
            .withColumnRenamed("haltestellen_name", "stop_name")
            .withColumnRenamed("ankunftszeit", "arrival_time_table")
            .withColumnRenamed("an_prognose", "arrival_time_real")
            .withColumnRenamed("an_prognose_status", "arrival_forecast_status")
            .withColumnRenamed("abfahrtszeit", "departure_time_table")
            .withColumnRenamed("ab_prognose", "departure_time_real")
            .withColumnRenamed("ab_prognose_status", "departure_forecast_status")
            .withColumnRenamed("durchfahrt_tf", "transit_tf")
            .withColumnRenamed("year", "year")
            .withColumnRenamed("month", "month")
           )

# Clean up null values in trips_df
trips_df = trips_df.na.drop()

# Ignore cancelled trips
filtered_trips_df = trips_df.filter(trips_df["is_cancelled_tf"] == "false")

# Selecting only relevant columns based on the delay detection requirement
columns_to_keep = ["product_id", 
    "arrival_time_table", "arrival_time_real",
    "departure_time_table", "departure_time_real"
]

# Filtering the DataFrame to keep only the necessary columns
filtered_trips_df = filtered_trips_df.select(columns_to_keep)

# Constructing a dynamic filter to exclude empty strings in these columns
non_empty_filters = [col(column_name) != "" for column_name in columns_to_keep]

# Combine all conditions into one
combined_filter = reduce(lambda a, b: a & b, non_empty_filters, lit(True))

# Apply the combined filter to the DataFrame
filtered_trips_df = filtered_trips_df.filter(combined_filter)

casted_trips_df = filtered_trips_df

time_format = "dd.MM.yyyy HH:mm"
forecast_format = "dd.MM.yyyy HH:mm:ss"

# Convert time columns to timestamp type using the specified format
casted_trips_df = casted_trips_df.withColumn("arrival_time_table", to_timestamp("arrival_time_table", time_format))
casted_trips_df = casted_trips_df.withColumn("arrival_time_real", to_timestamp("arrival_time_real", forecast_format))
casted_trips_df = casted_trips_df.withColumn("departure_time_table", to_timestamp("departure_time_table", time_format))
casted_trips_df = casted_trips_df.withColumn("departure_time_real", to_timestamp("departure_time_real", forecast_format))

# Show the updated schema to verify changes
casted_trips_df.printSchema()

# Calculate arrival and departure delays in minutes
casted_trips_df = casted_trips_df.withColumn(
    "arrival_delay_minutes",
    (unix_timestamp("arrival_time_real") - unix_timestamp("arrival_time_table")) / 60
)

# %% [markdown]
# ### b) Feature Vector Construction using Spark MLlib

# %%
# Sample approximately 10% of the data without replacement (due to resources)
df = casted_trips_df.sample(False, 0.1, seed=42)

df = df.withColumn("label", when(df.arrival_delay_minutes <= 5, 0)
                   .otherwise(1))

# Extracting features from timestamps
df = df.withColumn("arrival_hour_table", hour(df.arrival_time_table))
df = df.withColumn("departure_hour_table", hour(df.departure_time_table))
df = df.withColumn("day_of_week", dayofweek(df.arrival_time_table))

# Define the feature columns and VectorAssembler
feature_columns = ['arrival_hour_table', 'departure_hour_table', 'day_of_week']
assembler = VectorAssembler(inputCols=feature_columns, outputCol="features")

# Apply the VectorAssembler to transform the data
vectorized_df = assembler.transform(df)

# Define the StandardScaler
scaler = StandardScaler(inputCol="features", outputCol="scaledFeatures", withStd=True, withMean=False)

# Create a Pipeline that includes both VectorAssembler and StandardScaler
pipeline = Pipeline(stages=[assembler, scaler])

# Fit the Pipeline to your data
pipelineModel = pipeline.fit(df)

# Save the Pipeline model to a directory
pipeline_path = "pipeline/delayed_trips"
pipelineModel.write().overwrite().save(pipeline_path)

# %%
# Apply the Pipeline model to transform the data
transformed_df = pipelineModel.transform(df)

# Split the data into training and validation sets
train_data, validation_data = transformed_df.randomSplit([0.8, 0.2], seed=42)

# %%
# Train the Logistic Regression model
lr = LogisticRegression(featuresCol="scaledFeatures", labelCol="label")
lr_model = lr.fit(train_data)

# Save the model
model_path = "model/logisitic_regression"
lr_model.write().overwrite().save(model_path)

# %% [markdown]
# ### c) Model evaluation

# %%
# Creating the evaluator
evaluator = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction")

# Evaluating accuracy
accuracy = evaluator.evaluate(lr_model.transform(validation_data))
print(f"Accuracy: {accuracy:.2f}")

# Evaluating precision
evaluator.setMetricName("weightedPrecision")
precision = evaluator.evaluate(lr_model.transform(validation_data))
print(f"Precision: {precision:.2f}")

# Evaluating recall
evaluator.setMetricName("weightedRecall")
recall = evaluator.evaluate(lr_model.transform(validation_data))
print(f"Recall: {recall:.2f}")

# Evaluating F1-score
evaluator.setMetricName("f1")
f1 = evaluator.evaluate(lr_model.transform(validation_data))
print(f"F1 Score: {f1:.2f}")

# %% [markdown]
# # 2. Compute delay probability of a single trip

# %%
from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
from pyspark.ml.classification import LogisticRegressionModel
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, IntegerType
from pyspark.sql.functions import hour, dayofweek, to_timestamp

def make_prediction(spark, sample, pipeline_path="pipeline/delayed_trips", model_path="model/logisitic_regression"):
    """
    Predict the probability of delay using a saved feature transformation pipeline and logistic regression model.
    
    Parameters:
        spark (SparkSession): The active Spark session.
        sample (tuple): Sample data as a tuple with fields (product_id, arrival_time, departure_time, day_of_week).
        pipeline_path (str): The path to the saved pipeline model for feature processing.
        model_path (str): The path to the saved logistic regression model for prediction.
        
    Returns:
        float: The probability of delay for the sample.
    """
    # Load the pipeline and model
    pipeline_model = PipelineModel.load(pipeline_path)
    logistic_model = LogisticRegressionModel.load(model_path)
    
    # Define schema based on the expected input for the model
    schema = StructType([
        StructField("product_id", StringType(), True),
        StructField("arrival_time_table", StringType(), True),
        StructField("departure_time_table", StringType(), True),
    ])
    
    # Create a DataFrame from the sample
    sample_df = spark.createDataFrame([sample], schema=schema)

    # Convert string timestamps to TimestampType
    sample_df = sample_df.withColumn("arrival_time_table", to_timestamp("arrival_time_table"))
    sample_df = sample_df.withColumn("departure_time_table", to_timestamp("departure_time_table"))

    # Calculate additional necessary columns if needed
    sample_df = sample_df.withColumn("arrival_hour_table", hour("arrival_time_table"))
    sample_df = sample_df.withColumn("departure_hour_table", hour("departure_time_table"))
    sample_df = sample_df.withColumn("day_of_week", dayofweek("arrival_time_table"))

    # Transform the sample using the pipeline
    transformed_sample = pipeline_model.transform(sample_df)

    # Make a prediction
    prediction = logistic_model.transform(transformed_sample)
    
    # Extract the probability of delay
    probability_of_delay = prediction.select("probability").head()[0][1]
    
    return probability_of_delay


# %%
# Example usage
# The arguments should be in the following order: product_id (produkt_id), arrival_time (ankunftszeit), departure_time (abfahrtszeit)
# For now the product_id is not used in the model prediction. Trying to solve it.
sample = ("123", "2023-05-26 15:04:00", "2023-05-26 15:30:00")

probability = make_prediction(spark, sample)
print("Probability of delay:", probability)

# %%
