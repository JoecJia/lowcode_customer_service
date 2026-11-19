
<font color="#dd0000">****\*注：表单、审批填写页地址追加 precast参数请求，目前仅支持单行输入、数字输入、日期、多行输入、联系人、所属人、单选、下拉框、图片、附件、视频、富文本及子表单中以上支持字段****</font>

*   <font color="#e1489f">**富文本字段特殊处理**</font>：需要按照笔记富文本格式传入（带标签样式），且需要两个参数详见文末json结构示例，参考文档：[https://sharewh2.xuexi365.com/share/bef1683c-dbce-4f65-821b-ee25f4e93cf9?t=3](https://sharewh2.xuexi365.com/share/bef1683c-dbce-4f65-821b-ee25f4e93cf9?t=3)
    

**​**  

*   **模拟post请求构造请求Demo：**  
    

```javascript
    var param = {'data': [{'alias': 1, 'val': ['123'], 'compt': 'editinput'}]}
	// 创建表单
	var temp_form = document.createElement('form')
	// 填写表单数据
	temp_form.action = 'http://t.chaoxing.com/front/web/apps/forms/fore/apply?id=51893&fidEnc=961400943d52d5e3&enc=af9fbe45c36aa24d5b662d81d831fe0c'
	temp_form.target = '_blank'
	temp_form.method = 'post'
	temp_form.style.display = 'none'
	// 添加参数
	var opt = document.createElement('textarea')
	opt.name = 'precast'
	opt.value = JSON.stringify(param)
	temp_form.appendChild(opt)
	document.body.appendChild(temp_form)
	// 提交数据
	temp_form.submit()
```
*   **get请求构造请求Demo：**  
原填写页地址后直接追加precast参数（编码）

*   **参数结构：**
```json

	{
    "data":[
        {
            "alias":1,
            "val":[
                "单行输入"
            ],
            "compt":"editinput"
        },
        {
            "alias":2,
            "val":[
                "多行输入"
            ],
            "compt":"editTextarea"
        },
        {
            "alias":3,
            "val":[
                "123456"
            ],
            "compt":"numberInput"
        },
        {
            "alias":4,
            "val":[
                "2021-09-03 00:00"
            ],
            "compt":"dateInput"
        },
        {
            "alias":5,
            "val":[
                [
                    {
                        "puid":73361131,
                        "uname":"张虎成"
                    }
                ]
            ],
            "compt":"contact"
        },
        {
            "alias":6,
            "val":[
                [
                    {
                        "puid":73361131,
                        "uname":"张虎成"
                    }
                ]
            ],
            "compt":"belonger"
        },
        {
            "alias":7,
            "val":[
                {
                    "val":"选项1"
                }
            ],
            "compt":"radiobutton"
        },
		{
			"alias": 111,
			"compt": "checklist",
			"val": [
				{
					"val": "选项1"
				},
				{
					"val": "选项2"
				}
			]
		},
        {
            "alias":8,
            "val":[
                {
                    "val":"选项2"
                }
            ],
            "compt":"selectbox"
        },
        {
            "alias":"9",
            "val":[
                {
                    "byteSize":"92815",
                    "duration":"0",
                    "fileUrl":"http://pan-yz.chaoxing.com/thumbnail/origin/d40d4cdf4e7ebe2f9c0bb7952bbd558e",
                    "modifyDate":1667876442261,
                    "name":"zhuomian.jpg",
                    "objectId":"d40d4cdf4e7ebe2f9c0bb7952bbd558e",
                    "puid":73361131,
                    "resid":"796694800379404300",
                    "size":"90.64KB",
                    "suffix":"jpg"
                }
            ],
            "compt":"imagebox"
        },
        {
            "alias":"10",
            "val":[
                {
                    "byteSize":"92815",
                    "duration":"0",
                    "modifyDate":1667876448412,
                    "name":"zhuomian.jpg",
                    "objectId":"d40d4cdf4e7ebe2f9c0bb7952bbd558e",
                    "puid":73361131,
                    "resid":"796694826177376256",
                    "size":"90.64KB",
                    "suffix":"jpg"
                }
            ],
            "compt":"fileupload"
        },
        {
            "alias":"11",
            "val":[
                {
                    "byteSize":"439497",
                    "duration":"0",
                    "fileUrl":"http://pan-yz.chaoxing.com/thumbnail/origin/abec7d95818c1117b53657770c504ade",
                    "modifyDate":1667876560894,
                    "name":"test.mp4",
                    "objectId":"abec7d95818c1117b53657770c504ade",
                    "puid":73361131,
                    "resid":"796695298581835800",
                    "size":"429.2KB",
                    "suffix":"mp4",
                    "videoHeight":"0",
                    "videoWidth":"0"
                }
            ],
            "compt":"videobox"
        },
        {
            "alias":"12",
            "val":[
                "富文本内容（咨询笔记如何获取）"
            ],
            "content":"富文本full_content内容（咨询笔记如何获取）",
            "compt":"richtext"
        },
        {
            "alias":"13",
            "compt":"detailcombox",
            "rows":[
                [
                    {
                        "alias":"14",
                        "compt":"editinput",
                        "val":[
                            "子表单单行输入"
                        ]
                    },
                    {
                        "alias":"15",
                        "compt":"edittextarea",
                        "val":[
                            "子表单多行输入"
                        ]
                    },
                    {
                        "alias":16,
                        "val":[
                            "123456"
                        ],
                        "compt":"numberInput"
                    },
                    {
                        "alias":17,
                        "val":[
                            "2021-09-03 00:00"
                        ],
                        "compt":"dateInput"
                    },
                    {
                        "alias":18,
                        "val":[
                            [
                                {
                                    "puid":73361131,
                                    "uname":"张虎成"
                                }
                            ]
                        ],
                        "compt":"contact"
                    },
                    {
                        "alias":19,
                        "val":[
                            {
                                "val":"选项1"
                            }
                        ],
                        "compt":"radiobutton"
                    },
                    {
                        "alias":20,
                        "val":[
                            {
                                "val":"选项2"
                            }
                        ],
                        "compt":"selectbox"
                    },
                    {
                        "alias":"21",
                        "val":[
                            {
                                "byteSize":"92815",
                                "duration":"0",
                                "fileUrl":"http://pan-yz.chaoxing.com/thumbnail/origin/d40d4cdf4e7ebe2f9c0bb7952bbd558e",
                                "modifyDate":1667876442261,
                                "name":"zhuomian.jpg",
                                "objectId":"d40d4cdf4e7ebe2f9c0bb7952bbd558e",
                                "puid":73361131,
                                "resid":"796694800379404300",
                                "size":"90.64KB",
                                "suffix":"jpg"
                            }
                        ],
                        "compt":"imagebox"
                    },
                    {
                        "alias":"22",
                        "val":[
                            {
                                "byteSize":"92815",
                                "duration":"0",
                                "modifyDate":1667876448412,
                                "name":"zhuomian.jpg",
                                "objectId":"d40d4cdf4e7ebe2f9c0bb7952bbd558e",
                                "puid":73361131,
                                "resid":"796694826177376256",
                                "size":"90.64KB",
                                "suffix":"jpg"
                            }
                        ],
                        "compt":"fileupload"
                    },
                    {
                        "alias":"23",
                        "val":[
                            {
                                "byteSize":"439497",
                                "duration":"0",
                                "fileUrl":"http://pan-yz.chaoxing.com/thumbnail/origin/abec7d95818c1117b53657770c504ade",
                                "modifyDate":1667876560894,
                                "name":"test.mp4",
                                "objectId":"abec7d95818c1117b53657770c504ade",
                                "puid":73361131,
                                "resid":"796695298581835800",
                                "size":"429.2KB",
                                "suffix":"mp4",
                                "videoHeight":"0",
                                "videoWidth":"0"
                            }
                        ],
                        "compt":"videobox"
                    }
                ]
            ]
        }
    ]
}
```
