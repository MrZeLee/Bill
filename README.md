# Bill

## Build

```bash
docker build -t bill .
```

## Run

```
docker run -v /path/to/service-account.json:/app/service-account.json -v /path/to/.env:/app/.env bill
```
