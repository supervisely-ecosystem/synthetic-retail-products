<div align="center" markdown>
<img src="https://i.imgur.com/nOVbVMv.png"/>

# Generate Synthetic Retail Products

<p align="center">
  <a href="#Overview">Overview</a> •
  <a href="#How-To-Use">How To Use</a> •
    <a href="#Screenshots">Screenshots</a>
</p>


[![](https://img.shields.io/badge/supervisely-ecosystem-brightgreen)](https://ecosystem.supervise.ly/apps/synthetic-retail-products)
[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervise.ly/slack)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/synthetic-retail-products)
[![views](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/synthetic-retail-products&counter=views&label=views)](https://supervise.ly)
[![used by teams](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/synthetic-retail-products&counter=downloads&label=used%20by%20teams)](https://supervise.ly)
[![runs](https://app.supervise.ly/public/api/v3/ecosystem.counters?repo=supervisely-ecosystem/synthetic-retail-products&counter=runs&label=runs)](https://supervise.ly)

</div>

# Overview

App generates synthetic data for classification and segmentation tasks. This data can be successfully used to train classification or segmentation models and then use them to recognize and classify products on grocery store shelves.

# How To Use


1. Prepare your data: label products with polygons or bitmaps, assign tag (product identifier) to every labeled object. For example, if you have 50 items in your catalog, project will have 50 tags and just label at least one example for every item in a catalog and assign corresponding tag to the object.  You can use ready example project [Snacks Catalog](https://ecosystem.supervise.ly/projects/snacks-catalog) from ecosystem. In this demo project we labeled one object per image. You can label several objects on a single image (for example: if you want to label examples on photos of product shelves).

<img  data-key="sly-module-link" data-module-slug="supervisely-ecosystem/snacks-catalog" src="https://i.imgur.com/7YPoLGY.png" width="450"/> 

2. Add app from ecosystem to your team

<img  data-key="sly-module-link" data-module-slug="supervisely-ecosystem/synthetic-retail-products" src="https://i.imgur.com/MLR6Kkm.png" width="450"/>   

3. Run app from the context menu of labeled project. App will cache all objects with tags, object will be skipped if object doesn't have tag or has more than one tag 

4. Configure augmentations and preview examples in realtime
   
5. Once you are ready with augmentations settings, define output project and press `Generate` button
   
6. New project with synthetic data will be created, app will be closed automatically. For every product in  labeled catalog will be created a separate dataset, synthetic images have object mask, tag of the product (i.e. product id), and `train` or `val` tag (defines if the image is in training or validation set).


**Watch demo video**:


<a data-key="sly-embeded-video-link" href="https://youtu.be/DazA1SSQOK8" data-video-code="DazA1SSQOK8">
    <img src="https://i.imgur.com/TDGyy1E.png" alt="SLY_EMBEDED_VIDEO_LINK"  style="max-width:100%;">
</a>

# Screenshots

<img src="https://i.imgur.com/izY9tR7.png"/>