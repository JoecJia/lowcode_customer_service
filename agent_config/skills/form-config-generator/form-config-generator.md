---
name: "form-config-generator"
description: "Generates form configuration JSON files with field definitions, validation rules, and UI layout. Invoke when user asks to create form config, form schema, or form template."
---

# Form Config Generator

This skill generates form configuration files in JSONC format (JSON with Comments).

## Form Configuration Format

Each form configuration file defines the structure of a form, including fields, validation rules, layout, and submission settings.

### Configuration Structure

```jsonc
{
  "form": {
    // 表单唯一标识
    "id": "string",
    // 表单名称
    "name": "string",
    // 表单描述
    "description": "string",
    // 提交接口地址
    "action": "string",
    // 请求方法: POST | PUT | PATCH
    "method": "POST",
    // 表单布局: horizontal | vertical | inline
    "layout": "vertical",
    // 标签宽度(px)
    "labelWidth": 100,
    // 提交按钮文本
    "submitText": "提交",
    // 重置按钮文本，为空则不显示
    "resetText": "重置"
  },
  "fields": [
    {
      // 字段唯一标识
      "name": "field_name",
      // 字段类型: input | textarea | select | radio | checkbox | switch | datepicker | timepicker | upload | number | password | email
      "type": "input",
      // 字段标签
      "label": "字段标签",
      // 占位符文本
      "placeholder": "请输入",
      // 默认值
      "defaultValue": "",
      // 是否必填
      "required": true,
      // 是否禁用
      "disabled": false,
      // 是否只读
      "readonly": false,
      // 提示信息
      "tooltip": "",
      // 校验规则列表
      "rules": [
        {
          // 校验类型: required | pattern | min | max | minLength | maxLength | email | url | custom
          "type": "required",
          // 校验失败提示
          "message": "该字段为必填项",
          // 正则表达式(当 type 为 pattern 时)
          "pattern": "",
          // 最小值/最小长度
          "min": null,
          // 最大值/最大长度
          "max": null
        }
      ],
      // 选项列表(当 type 为 select/radio/checkbox 时)
      "options": [
        {
          "label": "选项1",
          "value": "value1"
        }
      ],
      // 控件额外属性
      "props": {}
    }
  ],
  // 分组配置(可选)
  "groups": [
    {
      // 分组标题
      "title": "基础信息",
      // 该分组包含的字段名列表
      "fields": ["name", "age"],
      // 是否可折叠
      "collapsible": false,
      // 默认折叠
      "collapsed": false
    }
  ]
}
```

## Usage

When asked to generate a form configuration:
1. Ask the user what fields they need and their types
2. Confirm validation rules and layout preferences
3. Generate the `.jsonc` form configuration file

## File Naming

Form config files should be named as `<form-name>-form.jsonc` and placed in an appropriate directory (e.g., `configs/forms/` or `src/forms/`).
