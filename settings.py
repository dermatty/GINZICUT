# options
savefiles = False

# debug
debug_level = "debug"

# ginzicut server
nntp_hostname = "0.0.0.0"
nntp_port = 7016
max_connections = 12

# server_type
server_type = "read-only"

# forwarding
do_forwarding = True
forward_server_url = "xxxx.yyyy.eu"
forward_server_user = "user"
forward_server_pass = "password"
forward_server_port = 563 
forward_server_ssl = True

### redis
use_redis = True
# if tcp is used
redis_tcp = False
redis_port = 6379
redis_host = "127.0.0.1"
# for unix-sockets (faster)
#	in /etc/redis.conf set:
#          unixsocket /var/run/redis/redis.sock
#          unixsocketperm 775
#       sudo chown redis:redis /var/run/redis/redis.sock
#       sudo chmod 777 /var/run/redis/redis.sock
redis_unix = True
unix_socket_path = "/var/run/redis/redis.sock"
