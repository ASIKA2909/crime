from better_profanity import profanity
from flask import Flask,render_template,request,redirect,url_for
import mysql.connector
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfTransformer, CountVectorizer, TfidfVectorizer
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from nltk.stem.porter import PorterStemmer
import nltk
import re, string
from nltk.corpus import stopwords
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score
from sklearn.metrics import precision_recall_curve
from sklearn.metrics import plot_precision_recall_curve
from sklearn.metrics import roc_auc_score
from sklearn.metrics import roc_curve
from sklearn.metrics import classification_report
from sklearn import metrics
from imblearn.over_sampling import RandomOverSampler

UPLOAD_FOLDER = 'static/file/'
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/loginpost.html', methods = ['POST','GET'])
def userloginpost():
    if request.method == 'POST':
        data1 = request.form.get('username')
        data2 = request.form.get('password')
        mydb = mysql.connector.connect(host="localhost",user="root",password="",database="cyber")
        mycursor = mydb.cursor()
        sql = "SELECT * FROM `users` WHERE `name` = %s AND `password` = %s"
        val = (data1, data2)
        mycursor.execute(sql,val)
        account = mycursor.fetchone()
        if account:
            return render_template('twitter.html')
        elif data1 == 'Admin' and data2 == 'Admin':
            return render_template('dashboard.html')
        else:
            return render_template('login.html',msg = 'Invalid')
@app.route('/pages-register.html')
def reg():
    return render_template('pages-register.html')

@app.route('/reg',methods=['POST','GET'])
def register():
    if request.method == 'POST':
        name = request.form.get('username')
        phone = request.form.get('phone')
        password = request.form.get('password')
        mydb = mysql.connector.connect(host="localhost",user="root",password="",database="cyber")
        mycursor = mydb.cursor()
        sql = "INSERT INTO users (`name`, `phone`, `password`) VALUES (%s, %s, %s)"
        val = (name,phone,password)
        mycursor.execute(sql, val)
        mydb.commit()
        return render_template('login.html')

@app.route('/send',methods=['POST','GET'])
def send():
    if request.method == 'POST':
        msg = request.form.get('msg')
        censored = profanity.censor(msg)
        if '*' in censored:
            return render_template('twitter.html',view = 'style=display:block', value = 'Hello user! You send wrong word Please Change it!')
        else:
            return render_template('twitter.html',view = 'style=display:block', value = 'Post Tweeted')

@app.route('/upload.html')
def up():
    return render_template('upload.html')

@app.route('/upload',methods=['POST','GET'])
def upload():
    global df
    if request.method == 'POST':
        if os.path.exists('static/file/perform.png'):
            os.remove('static/file/perform.png')
        if os.path.exists('static/file/abc.png'):
            os.remove('static/file/abc.png')
        if os.path.exists('static/file/dtc.png'):
            os.remove('static/file/dtc.png')
        if os.path.exists('static/file/gnb.png'):
            os.remove('static/file/gnb.png')
        if os.path.exists('static/file/lgr.png'):
            os.remove('static/file/lgr.png')
        if os.path.exists('static/file/rfc.png'):
            os.remove('static/file/rfc.png')
        file1 = request.files['jsonfile']
        if file1:
            jsonfile = os.path.join(app.config['UPLOAD_FOLDER'], file1.filename)
            file1.save(jsonfile)
        else:
            jsonfile = 'static/file/Dataset.json'
        df = pd.read_json(jsonfile)
        for i in range(0,len(df)):
            if df.annotation[i]['label'][0] == '1':
                df.annotation[i] = 1
            else:
                df.annotation[i] = 0
        df.drop(['extras'],axis = 1,inplace = True)
        df['annotation'].value_counts().sort_index().plot.bar()
        plt.savefig('static/file/perform.png')

        # pre processing

        nltk.download('stopwords')
        stop = stopwords.words('english')
        regex = re.compile('[%s]' % re.escape(string.punctuation))
        def test_re(s):
            return regex.sub('', s)
        df ['content_without_stopwords'] = df['content'].apply(lambda x: ' '.join([word for word in x.split() if word not in (stop)]))
        df ['content_without_puncs'] = df['content_without_stopwords'].apply(lambda x: regex.sub('',x))
        del df['content_without_stopwords']
        del df['content']

        #Stemming
        porter_stemmer = PorterStemmer()
        #punctuations
        nltk.download('punkt')
        tok_list = []
        size = df.shape[0]
        for i in range(size):
            word_data = df['content_without_puncs'][i]
            nltk_tokens = nltk.word_tokenize(word_data)
            final = ''
            for w in nltk_tokens:
                final = final + ' ' + porter_stemmer.stem(w)
            tok_list.append(final)
        df['content_tokenize'] = tok_list
        del df['content_without_puncs']

        noNums = []
        for i in range(len(df)):
            noNums.append(''.join([i for i in df['content_tokenize'][i] if not i.isdigit()]))
        df['content'] = noNums

        tfIdfVectorizer=TfidfVectorizer(use_idf=True, sublinear_tf=True)
        tfIdf = tfIdfVectorizer.fit_transform(df.content.tolist())

        df2 = pd.DataFrame(tfIdf[2].T.todense(), index=tfIdfVectorizer.get_feature_names(), columns=["TF-IDF"]) #for second entry only(just to check if working)
        df2 = df2.sort_values('TF-IDF', ascending=False)

        dfx = pd.DataFrame(tfIdf.toarray(), columns = tfIdfVectorizer.get_feature_names())

        def display_scores(vectorizer, tfidf_result):
            scores = zip(vectorizer.get_feature_names(),
                np.asarray(tfidf_result.sum(axis=0)).ravel())
            sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
            i=0
            for item in sorted_scores:
                print ("{0:50} Score: {1}".format(item[0], item[1]))
                i = i+1
                if (i > 25):
                    break
        display_scores(tfIdfVectorizer, tfIdf)

        X=tfIdf.toarray()
        y = np.array(df.annotation.tolist())
        #Spltting
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

        #Training data biasness
        unique_elements, counts_elements = np.unique(y_train, return_counts=True)
        unique_elements, counts_elements = np.unique(y_test, return_counts=True)

        oversample = RandomOverSampler(sampling_strategy='not majority')
        X_over, y_over = oversample.fit_resample(X_train, y_train)

        unique_elements, counts_elements = np.unique(y_over, return_counts=True)

        def getStatsFromModel(model):
            # print(classification_report(y_test, y_pred))
            disp = plot_precision_recall_curve(model, X_test, y_test)
            disp.ax_.set_title('2-class Precision-Recall curve: ''AP={0:0.2f}')
            logit_roc_auc = roc_auc_score(y_test, model.predict(X_test))
            fpr, tpr, thresholds = roc_curve(y_test, model.predict_proba(X_test)[:,1])
            plt.figure()
            plt.plot(fpr, tpr, label='(area = %0.2f)' % logit_roc_auc)
            plt.plot([0, 1], [0, 1],'r--')
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title('Receiver operating characteristic')
            plt.legend(loc="lower right")
            # plt.savefig('static/file/roc.png')

        gnb = GaussianNB()
        gnbmodel = gnb.fit(X_over, y_over)
        y_pred = gnbmodel.predict(X_test)
        print ("Score:", gnbmodel.score(X_test, y_test))
        # print("Confusion Matrix: \n", confusion_matrix(y_test, y_pred))
        plt.title('GaussianNB')
        getStatsFromModel(gnb)
        plt.savefig('static/file/gnb.png')

        lgr = LogisticRegression()
        lgr.fit(X_over, y_over)
        y_pred = lgr.predict(X_test)
        # print("Accuracy: ",metrics.accuracy_score(y_test, y_pred))
        # print("Confusion Matrix: \n", confusion_matrix(y_test, y_pred))
        plt.title('Logistic Regression')
        getStatsFromModel(lgr)
        plt.savefig('static/file/lgr.png')

        dtc = DecisionTreeClassifier()
        dtc.fit(X_over, y_over)
        y_pred = dtc.predict(X_test)
        # print("Accuracy: ",metrics.accuracy_score(y_test, y_pred))
        # print("Confusion Matrix: \n", confusion_matrix(y_test, y_pred))
        plt.title('Decision Tree Classifier')
        getStatsFromModel(dtc)
        plt.savefig('static/file/dtc.png')

        abc = AdaBoostClassifier() 
        abc.fit(X_over, y_over)
        y_pred = abc.predict(X_test)
        # print("Accuracy: ",metrics.accuracy_score(y_test, y_pred))
        # print("Confusion Matrix: \n", confusion_matrix(y_test, y_pred))
        plt.title('AdaBoost')
        getStatsFromModel(abc)
        plt.savefig('static/file/abc.png')

        rfc = RandomForestClassifier(verbose=True) #uses randomized decision trees
        rfcmodel = rfc.fit(X_over, y_over)
        y_pred = rfc.predict(X_test)
        # print ("Score:", rfcmodel.score(X_test, y_test))
        # print("Confusion Matrix: \n", confusion_matrix(y_test, y_pred))
        getStatsFromModel(rfc)
        plt.savefig('static/file/rfc.png')

        return render_template('upload.html',msg='File Upload Successfully...')

@app.route('/dashboard.html')
def dashboard():
    return render_template('dashboard.html')

@app.route('/performence')
def performence():
    return render_template('perform.html',path='static/file/perform.png')
@app.route('/gnb')
def gnb():
    return render_template('gnb.html',path='static/file/gnb.png')
@app.route('/lgr')
def lgr():
    return render_template('lgr.html',path='static/file/lgr.png')
@app.route('/dtc')
def dtc():
    return render_template('dtc.html',path='static/file/dtc.png')
@app.route('/abc')
def abc():
    return render_template('abc.html',path='static/file/abc.png')
@app.route('/rfc')
def rfc():
    return render_template('rfc.html',path='static/file/rfc.png')

if __name__ == '__main__':
    app.run(debug=True,port=2000)