from pyspark.sql.functions import input_file_name
from rake_nltk import RakeKeywordExtractor
from pyspark.sql.types import *
from pyspark.sql import SparkSession
import nltk
from pyspark.sql import SQLContext
from nltk.corpus import stopwords 
from nltk.tokenize import word_tokenize
from ast import literal_eval
from operator import concat

def delete_path(spark, path):
    sc = spark.sparkContext
    fs = (sc._jvm.org
          .apache.hadoop
          .fs.FileSystem
          .get(sc._jsc.hadoopConfiguration())
          )
    fs.delete(sc._jvm.org.apache.hadoop.fs.Path(path), True)

def keywords_from_row(id, content, title, keywords, meta_keywords, meta_description, tags, summary, rake):
    keywords_exctracted = []
    if content is not None:
        keywords_from_content = rake.extract(str(content), True)
        for key_score in keywords_from_content:
            keywords_exctracted.append((key_score[0], id, key_score[1]))
    return (id, keywords_exctracted)

def get_processed_words(title):
    title = str(title.encode("ascii", "ignore"))
    if("/s/chopin/a/grad/joyghosh/nltk_data" not in nltk.data.path):
        nltk.data.path.append("/s/chopin/a/grad/joyghosh/nltk_data")
    stop_words = set(stopwords.words('english')) 
    return [w.lower() for w in word_tokenize(title) if (not w in stop_words and len(w) > 1)]

# 
# blank 0
# id	1, 0
# domain 2	
# type	3
# url	4
# content	5, 1
# scraped_at	6
# inserted_at	7
# updated_at	8
# title	9, 2
# authors	10
# keywords	11, 3
# meta_keywords	12, 4
# meta_description	13, 5
# tags	14, 6
# summary 15, 7


#inputfolderpath = "hdfs://santa-fe:47001/Source-Recommendation-System/FakeNewsCorpus/news_cleaned_2018_02_13.csv"
#inputfolderpath = "hdfs://santa-fe:47001/FakeNewsCorpus/news_cleaned_2018_02_13.csv"
inputfolderpath = "hdfs://santa-fe:47001/FakeNewsCorpus-Outputs/news_cleaned_partitioned/news_cleaned_2018_02_1300000"
#inputfolderpath = "hdfs://santa-fe:47001/Source-Recommendation-System/FakeNewsCorpus/news_sample.csv"
#outputfolderpath = "hdfs://santa-fe:47001/Source-Recommendation-System/FakeNewsCorpus-Outputs"
outputfolderpath = "hdfs://santa-fe:47001/FakeNewsCorpus-Outputs/KeywordsFromPartitions/news_cleaned_partitioned/news_cleaned_2018_02_1300000temp"


title_score = 10
keywords_score = 15
meta_keywords_score = 15
meta_description_score = 8
tags_score = 12
summary_score = 10

spark = SparkSession.builder.appName("ReadCSVFileFromFakeNewsPartitions").getOrCreate()
delete_path(spark, outputfolderpath)
#sc = SparkContext(master="spark://santa-fe:47002")
sqlContext = SQLContext(spark.sparkContext)
inputfile = sqlContext.read.csv(inputfolderpath, header=True,sep=",", multiLine = True, quote='"', escape='"')

inputfile = inputfile\
    .select("id", "content", "title", "keywords", "meta_keywords", "meta_description", "tags", "summary")

rake = RakeKeywordExtractor()

keywords_from_content = inputfile.rdd\
    .filter(lambda row : row["content"] is not None and row["content"] != "null")\
    .map(lambda  row : rake.extract_with_row_id(row["id"], row["content"], True))\
    .flatMap(lambda xs: [(x) for x in xs])
print("++++ Finished processing content column")

keywords_from_title = inputfile.rdd\
    .filter(lambda row : row["title"] is not None and row["title"] != "null")\
    .map(lambda row : [(x,"(" + str(row["id"]) + "," + str(title_score) + ")") for x in get_processed_words(row["title"])])\
    .flatMap(lambda xs: [(x) for x in xs])
print("++++ Finished processing title column")

keywords_from_keywords_col = inputfile.rdd\
    .filter(lambda row : row["keywords"] is not None and row["keywords"] != "null")\
    .map(lambda row : [(x.lower(),"(" + str(row["id"]) + "," + str(keywords_score) + ")") for x in str(row["keywords"].encode('ascii', "ignore")).split(" ")])\
    .flatMap(lambda xs: [(x) for x in xs])
#print(keywords_from_keywords_col.count())
print("++++ Finished processing keywords column")
keywords_from_meta_keywords = inputfile.rdd\
    .filter(lambda row : row["meta_keywords"] is not None and row["meta_keywords"] != "null")\
    .map(lambda row : [(x.lower(),"(" + str(row["id"]) + "," + str(meta_keywords_score) + ")") for x in literal_eval(row["meta_keywords"]) if len(x) > 1 ])\
    .flatMap(lambda xs: [(x) for x in xs])
print("++++ Finished processing meta_keywords column")
keywords_from_meta_description = inputfile.rdd\
    .filter(lambda row : row["meta_description"] is not None and row["meta_description"] != "null")\
    .map(lambda row : [(x, "(" + str(row["id"]) + "," + str(meta_description_score) + ")") for x in get_processed_words(row["meta_description"])])\
    .flatMap(lambda xs: [(x) for x in xs])
print("++++ Finished processing meta_description column")
keywords_from_tags = inputfile.rdd\
    .filter(lambda row : row["tags"] is not None and row["tags"] != "null")\
    .map(lambda row : [(x.lower(), "(" + str(row["id"]) + "," + str(tags_score) + ")") for x in str(row["tags"].encode('ascii', "ignore")).split(",") ])\
    .flatMap(lambda xs: [(x) for x in xs])
print("++++ Finished processing tags column")
keywords_from_summary = inputfile.rdd\
    .filter(lambda row : row["summary"] is not None and row["summary"] != "null")\
    .map(lambda  row : rake.extract_with_row_id(row["id"], row["summary"], True))\
    .flatMap(lambda xs: [(x) for x in xs])
print("++++ Finished processing summary column")

all_keywords_list = [keywords_from_content, keywords_from_title, keywords_from_keywords_col, keywords_from_meta_keywords,
    keywords_from_meta_description, keywords_from_tags, keywords_from_summary]

all_keywords_rdd = spark.sparkContext.union(all_keywords_list)
all_keywords_rdd = all_keywords_rdd\
    .filter(lambda row: len(row[0]) > 2)

# all_keywords_rdd = all_keywords_rdd.groupByKey()\
#         .map(lambda key_rows : (key_rows[0], list(key_rows[1])))
#all_keywords_rdd = all_keywords_rdd.reduceByKey(concat)

#print("++++ Finished groupBy")
schema = StructType([   
        StructField("Keyword", StringType(), False),
        StructField("RowId & Score", StringType(), False)
    ])
#all_keywords_rdd = keywords_from_content
all_keywords_df = spark.createDataFrame(all_keywords_rdd, schema=schema)
#all_keywords_df = all_keywords_df.sort(all_keywords_df.Keyword)
print("++++ Finished sorting")
all_keywords_df.write.csv(outputfolderpath, header=True, quote='"', escape='"')
print("++++ Finshed saving")

spark.stop()
