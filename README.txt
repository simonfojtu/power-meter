POWER METER
===========


### Pushing web pages to a ftp server for public display

e.g. by cron every 5 minutes

    */5 * * * * for f in path/to/www/*; do curl -T $f ftp://remote.server/subdirectory/ --user username:password > /dev/null; done
