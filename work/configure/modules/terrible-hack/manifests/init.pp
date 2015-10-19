class terrible-hack {
    file { ['/var/www', '/var/www/example.com', '/var/www/example.com/html']:
        ensure => directory,
        owner  => root,
        group  => root,
        mode   => 0755
    } ->
    file { '/etc/nginx/conf.d/example.conf':
        ensure => present,
        owner  => root,
        group  => root,
        mode   => 0755,
        source => "puppet:///modules/terrible-hack/example.conf"
    } ->
    exec { "restart-nginx":
        command => "/sbin/service nginx restart",
        user    => root,
    }
}
