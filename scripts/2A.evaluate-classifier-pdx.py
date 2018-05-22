
# coding: utf-8

# # Evaluate Predictions Made on PDX Samples
# 
# **Gregory Way, 2018**
# 
# In the following notebook I evaluate the predictions made by the Ras and _TP53_ classifiers in the input PDX RNAseq data.
# 
# ## Procedure
# 
# 1. Load status matrices
#   * These files store the mutation status for _TP53_ and Ras pathway genes for the input samples
# 2. Align barcode identifiers
#   * The identifiers matching the RNAseq data to the status matrix are not aligned.
#   * I use an intermediate dictionary to map common identifiers
# 3. Load predictions (see `1.apply-classifier.ipynb` for more details)
# 4. Evaluate predictions
#   * I visualize the distribution of predictions between wild-type and mutant samples for both classifiers
# 
# ### Important Caveat
# 
# Many of the barcodes require updating.
# Some samples are not identified.
# I remove these samples from downstream evaluation, but discrepancies should be reconciled at a later date.
# 
# ## Output
# 
# The output of this notebook are several evaluation figures demonstrating the predictive performance on the input data for the two classifiers. Included in this output are predictions stratified by histology.

# In[1]:


import os
import random
from decimal import Decimal
from scipy.stats import ttest_ind
import numpy as np
import pandas as pd

from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.metrics import roc_curve, precision_recall_curve

import seaborn as sns
import matplotlib.pyplot as plt


# In[2]:


get_ipython().run_line_magic('matplotlib', 'inline')


# ## Load Ras Status Matrix

# In[3]:


file = os.path.join('data', 'raw', 'ras.genes.txt')
ras_status_df = pd.read_table(file)

print(ras_status_df.shape)
ras_status_df.head(3)


# In[4]:


len(ras_status_df.Model.unique())


# In[5]:


ras_status_df.Hugo_Symbol.value_counts()


# In[6]:


ras_status_df.Variant_Classification.value_counts()


# ## Load _TP53_ Status Matrix

# In[7]:


file = os.path.join('data', 'raw', 'tp53.muts.txt')
tp53_status_df = pd.read_table(file)
print(tp53_status_df.shape)
tp53_status_df.head(3)


# In[8]:


len(tp53_status_df.Model.unique())


# In[9]:


tp53_status_df.Hugo_Symbol.value_counts()


# In[10]:


tp53_status_df.Variant_Classification.value_counts()


# ## Load Clinical Data Information
# 
# This stores histology information

# In[11]:


file = os.path.join('data', 'raw', '2018-05-22-pdx-clinical.txt')
clinical_df = pd.read_table(file)

# Make every histology with the word `Other` in it in the same class
clinical_df.loc[clinical_df.Histology.str.contains('Other'), 'Histology'] = "Other"

print(clinical_df.shape)
clinical_df.head(3)


# In[12]:


clinical_df.Histology.value_counts()


# ## Load Predictions

# In[13]:


file = os.path.join('results', 'pdx_classifier_scores.tsv')
scores_df = pd.read_table(file)

print(scores_df.shape)
scores_df.head(3)


# In[14]:


scores_df = scores_df.merge(clinical_df, how='left', left_on='sample_id', right_on='Model')
print(scores_df.shape)
scores_df


# In[15]:


# Did any gene expression values fail to map to barcodes?
scores_df.Model.isna().value_counts()


# In[16]:


scores_df = (
    scores_df.merge(
        tp53_status_df.loc[:, ['Hugo_Symbol', 'Model']],
        how='left', left_on='Model', right_on='Model'
    )
    .merge(
        ras_status_df.loc[:, ['Hugo_Symbol', 'Model']],
        how='left', left_on='Model', right_on='Model',
        suffixes=('_tp53', '_ras')
    )
)

scores_df.head(2)


# In[17]:


scores_df = scores_df.assign(tp53_status = scores_df['Hugo_Symbol_tp53'])
scores_df = scores_df.assign(ras_status = scores_df['Hugo_Symbol_ras'])


# In[18]:


scores_df.loc[:, ['tp53_status', 'ras_status']] = (
    scores_df.loc[:, ['tp53_status', 'ras_status']].fillna(0)
)

scores_df.loc[:, ['Hugo_Symbol_tp53', 'Hugo_Symbol_ras']] = (
    scores_df.loc[:, ['Hugo_Symbol_tp53', 'Hugo_Symbol_ras']].fillna('wild-type')
)

scores_df.loc[scores_df['tp53_status'] != 0, 'tp53_status'] = 1
scores_df.loc[scores_df['ras_status'] != 0, 'ras_status'] = 1

scores_df.head(2)


# In[19]:


n_classes = 2

fpr_pdx = {}
tpr_pdx = {}
precision_pdx = {}
recall_pdx = {}
auroc_pdx = {}
aupr_pdx = {}

fpr_shuff = {}
tpr_shuff = {}
precision_shuff = {}
recall_shuff = {}
auroc_shuff = {}
aupr_shuff = {}

idx = 0
for status, score, shuff in zip(('ras_status', 'tp53_status'),
                                ('ras_score', 'tp53_score'),
                                ('ras_shuffle', 'tp53_shuffle')):
    
    # Obtain Metrics
    sample_status = scores_df.loc[:, status]
    sample_score = scores_df.loc[:, score]
    shuffle_score = scores_df.loc[:, shuff]
 
    # Get Metrics
    fpr_pdx[idx], tpr_pdx[idx], _ = roc_curve(sample_status, sample_score)
    precision_pdx[idx], recall_pdx[idx], _ = precision_recall_curve(sample_status, sample_score)
    auroc_pdx[idx] = roc_auc_score(sample_status, sample_score)
    aupr_pdx[idx] = average_precision_score(sample_status, sample_score)
    
    # Obtain Shuffled Metrics
    fpr_shuff[idx], tpr_shuff[idx], _ = roc_curve(sample_status, shuffle_score)
    precision_shuff[idx], recall_shuff[idx], _ = precision_recall_curve(sample_status, shuffle_score)
    auroc_shuff[idx] = roc_auc_score(sample_status, shuffle_score)
    aupr_shuff[idx] = average_precision_score(sample_status, shuffle_score)
    
    idx += 1


# In[20]:


if not os.path.exists('figures'):
    os.makedirs('figures')


# In[21]:


# Visualize ROC curves
plt.subplots(figsize=(4, 4))

labels = ['Ras', 'TP53']
colors = ['#1b9e77', '#d95f02']

for i in range(n_classes):
    plt.plot(fpr_pdx[i], tpr_pdx[i],
             label='{} (AUROC = {})'.format(labels[i], round(auroc_pdx[i], 2)),
             linestyle='solid',
             color=colors[i])

    # Shuffled Data
    plt.plot(fpr_shuff[i], tpr_shuff[i],
             label='{} Shuffle (AUROC = {})'.format(labels[i], round(auroc_shuff[i], 2)),
             linestyle='dotted',
             color=colors[i])

plt.axis('equal')
plt.plot([0, 1], [0, 1], 'k--')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.0])

plt.xlabel('False Positive Rate', fontsize=12)
plt.ylabel('True Positive Rate', fontsize=12)

plt.tick_params(labelsize=10)

lgd = plt.legend(bbox_to_anchor=(1.03, 0.85),
                 loc=2,
                 borderaxespad=0.,
                 fontsize=10)

file = os.path.join('figures', 'pdx_classifier_roc_curve.pdf')
#plt.savefig(file, bbox_extra_artists=(lgd,), bbox_inches='tight')


# In[22]:


# Visualize PR curves
plt.subplots(figsize=(4, 4))

for i in range(n_classes):
    plt.plot(recall_pdx[i], precision_pdx[i],
             label='{} (AUPR = {})'.format(labels[i], round(aupr_pdx[i], 2)),
             linestyle='solid',
             color=colors[i])
    
    # Shuffled Data
    plt.plot(recall_shuff[i], precision_shuff[i],
             label='{} Shuffle (AUPR = {})'.format(labels[i], round(aupr_shuff[i], 2)),
             linestyle='dotted',
             color=colors[i])

plt.axis('equal')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.0])

plt.xlabel('Recall', fontsize=12)
plt.ylabel('Precision', fontsize=12)

plt.tick_params(labelsize=10)

lgd = plt.legend(bbox_to_anchor=(1.03, 0.85),
                 loc=2,
                 borderaxespad=0.,
                 fontsize=10)

file = os.path.join('figures', 'pdx_classifier_precision_recall_curve.pdf')
#plt.savefig(file, bbox_extra_artists=(lgd,), bbox_inches='tight')


# In[23]:


# Output t-test results
t_results_ras = ttest_ind(a = scores_df.query('ras_status == 1').loc[:, 'ras_score'],
                          b = scores_df.query('ras_status == 0').loc[:, 'ras_score'],
                          equal_var = False)
t_results_ras


# In[24]:


# Output t-test results
t_results_tp53 = ttest_ind(a = scores_df.query('tp53_status == 1').loc[:, 'tp53_score'],
                          b = scores_df.query('tp53_status == 0').loc[:, 'tp53_score'],
                          equal_var = False)
t_results_tp53


# In[25]:


x1, x2 = 0, 1
x3, x4 = -0.2, 0.2
y1, y2, h = 0.98, 1, 0.03

plt.rcParams['figure.figsize']=(3.5, 4)
ax = sns.boxplot(x="ras_status",
                 y="ras_score",
                 data=scores_df,
                 palette = 'Greys',
                 fliersize=0)

ax = sns.stripplot(x="ras_status",
                   y="ras_score",
                   data=scores_df,
                   dodge=True,
                   edgecolor='black',
                   jitter=0.25,
                   size=4,
                   alpha=0.65)

ax.set_ylabel('Classifier Score', fontsize=12)
ax.set_xlabel('PDX Data', fontsize=12)
ax.set_xticklabels(['Ras Wild-Type', 'Ras Mutant'])

# Add Ras T-Test Results
plt.plot([x1, x1, x2, x2], [y1, y1+h, y1+h, y1], lw=1.2, c='black')
plt.text(.5, y1+h, "{:.2E}".format(Decimal(t_results_ras.pvalue)),
         ha='center', va='bottom', color="black")
plt.axhline(linewidth=2, y=0.5, color='black', linestyle='dashed')
plt.tight_layout()


file = os.path.join('figures', 'ras_predictions.pdf')
plt.savefig(file)


# In[26]:


x1, x2 = 0, 1
x3, x4 = -0.2, 0.2
y1, y2, h = 0.98, 1, 0.03

plt.rcParams['figure.figsize']=(3.5, 4)
ax = sns.boxplot(x="tp53_status",
                 y="tp53_score",
                 data=scores_df,
                 palette = 'Greys',
                 fliersize=0)

ax = sns.stripplot(x="tp53_status",
                   y="tp53_score",
                   data=scores_df,
                   dodge=True,
                   edgecolor='black',
                   jitter=0.25,
                   size=4,
                   alpha=0.65)

ax.set_ylabel('Classifier Score', fontsize=12)
ax.set_xlabel('PDX Data', fontsize=12)
ax.set_xticklabels(['TP53 Wild-Type', 'TP53 Mutant'])

# Add Ras T-Test Results
plt.plot([x1, x1, x2, x2], [y1, y1+h, y1+h, y1], lw=1.2, c='black')
plt.text(.5, y1+h, "{:.2E}".format(Decimal(t_results_tp53.pvalue)),
         ha='center', va='bottom', color="black")
plt.axhline(linewidth=2, y=0.5, color='black', linestyle='dashed');
plt.tight_layout()

file = os.path.join('figures', 'tp53_predictions.pdf')
plt.savefig(file)


# In[27]:


ax = sns.boxplot(x="ras_status",
                 y="ras_score",
                 data=scores_df,
                 hue='Histology',
                 palette = 'Greys',
                 fliersize=0)

ax = sns.stripplot(x="ras_status",
                   y="ras_score",
                   data=scores_df,
                   hue='Histology', 
                   dodge=True,
                   edgecolor='black',
                   jitter=0.25,
                   size=4,
                   alpha=0.65)

ax.set_ylabel('Classifier Score', fontsize=12)
ax.set_xlabel('Ras Status', fontsize=12)
plt.axhline(linewidth=2, y=0.5, color='black', linestyle='dashed')

handles, labels = ax.get_legend_handles_labels()
lgd = plt.legend(handles[15:31], labels[15:31],
               bbox_to_anchor=(1.03, 1),
                 loc=2,
                 borderaxespad=0.,
                 fontsize=10)

lgd.set_title("Histology")

file = os.path.join('figures', 'ras_predictions_histology.pdf')
plt.savefig(file, bbox_extra_artists=(lgd,), bbox_inches='tight')


# In[28]:


ax = sns.boxplot(x="tp53_status",
                 y="tp53_score",
                 data=scores_df,
                 hue='Histology',
                 palette = 'Greys',
                 fliersize=0)

ax = sns.stripplot(x="tp53_status",
                   y="tp53_score",
                   data=scores_df,
                   hue='Histology', 
                   dodge=True,
                   edgecolor='black',
                   jitter=0.25,
                   size=4,
                   alpha=0.65)

ax.set_ylabel('Classifier Score', fontsize=12)
ax.set_xlabel('TP53 Status', fontsize=12)
plt.axhline(linewidth=2, y=0.5, color='black', linestyle='dashed')

handles, labels = ax.get_legend_handles_labels()
lgd = plt.legend(handles[15:31], labels[15:31],
               bbox_to_anchor=(1.03, 1),
                 loc=2,
                 borderaxespad=0.,
                 fontsize=10)

lgd.set_title("Histology")

file = os.path.join('figures', 'tp53_predictions_histology.pdf')
plt.savefig(file, bbox_extra_artists=(lgd,), bbox_inches='tight')
