# 使用

1. 将blackbox目录放到blueJ的服务器上跑来生成新的数据：
    1. SSH连接BlueJ的服务器
    2. 修改`gen_compbos.py`中的用户名和密码
    3. 运行`build_blackbox_data.sh`
    4. 等待24小时左右，得到存在`src_files`目录下的数据
    5. 将`src_files`目录下的数据传输到本地

2. 获得试验结果
    1. 切换到`runnner`目录，运行`build.sh`.此命令会clone`grammars`和`gramtools`，并编译得到几个不同模式的`java_parser`
    2. 再运行`run.sh`，会使用上述的`java_parser`来处理之前获取的数据，并将结果写入`.csv`文件中。
    3. 这些结果只包含是否修复成功，修复成本等统计信息
    4. [ ] 将数据结果可视化

## 获得parser生成的patch
上述的运行指令只会得到修复结果的统计信息，但是我们希望比较不同工具的修复效果，则需要知道到底该工具到底生成了什么样的patch。

我们修改了`\runner\java_parser\src\main.rs`文件，增加了一句：

```Rust
println!("{}", e.pp(&lexer, &java7_y::token_epp));
```
重新编译，再进行解析时则会输出修改信息（生成文件路径：`\runner\java_parser\target\release\java_parser`），如：

```
Parsing error at line 177 column 14. Repair sequences found:
   1: Insert }
Error at line 177 col 14
Parsing error at line 180 column 12. Repair sequences found:
   1: Insert class, Insert <id>, Insert {
Error at line 180 col 12
```

# To-Dos

- [ ] 这些建议用户要如何采纳？是并列关系吗？
- [ ] 如何判断修复是否成功？
- [ ] 怎么把建议转换成diff？
- [ ] 能否从数据库中提取到编译过后的代码？ Sensibility中貌似有介绍