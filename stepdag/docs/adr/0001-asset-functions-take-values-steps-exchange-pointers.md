# Asset functions take values; steps exchange pointers through IO managers

Each asset runs as its own Lambda, and Step Functions passes state between them, limited to 256 KB. So a step's input is the parents' pointers, and its output is the pointer to what it stored. The asset's function never sees a pointer. Its IO manager loads each parent's value, the function returns a value, and the IO manager stores it and returns the pointer:

```python
@asset(deps=["shout", "word_count", "counter"], io_manager="run_json", memory=256)
def report(shout, words, count): ...
```

Parents are passed positionally, in `deps` order. Only their number is checked, so a parameter can be named anything. An asset that wants its previous materialization or the run's context declares the keyword-only parameters `previous` and `context`.

An asset names its IO manager; it doesn't choose it. Each environment binds the names to implementations: S3 in Lambda, S3 or a local directory in the CLI, and memory in tests. So a test of a whole graph needs no fake S3. Each IO manager decides where its values go. It is given the asset, the run's ID and an optional partition key, which nothing uses yet.

There are two executors over the same definitions. The Step Functions executor is a Lambda handler plus the rendered manifest (ADR 0005). The local executor runs every asset in one process, in dependency order, and still passes pointers between them, so it exercises the same path.

## Considered options

- **Functions that take and return pointers, doing their own reads and writes.** Rejected: every function would need S3 to test, and storage code would be repeated in every asset.
- **Parents passed as one dict,** or matched to parameters by name. Rejected: the dict is noisier to read, and name matching makes renaming a parameter a breaking change.
- **Locations chosen by the framework,** such as one per run per asset. Rejected: some assets need a fixed place, such as a cache that reads its own previous materialization or a published site, so only the IO manager can know.
