# Varstack

Varstack is a system that allows you to stack of layer a set of configuration variables and let definitions in the higher more specific levels of the stack override/extend the broader one in the lower levels.

To illustrate how this works let's consider an example:

First we need a configuration file for Varstack itself that defines which
configuration files to consider and in what order. The default path for this configuration file ist '/etc/varstack.yaml' and it looks like this:

```
datadir: /etc/varstack/stack
stack:
    - defaults
    - environments/%{env}
    - nodes/%{fqdn}
```

The 'datadir' setting defines the base directory which is searched for the configuration files specified in the 'stack' setting. The 'stack' setting is a list of configuration file candidates that will be read in the order they are specified if they exist. If a file doesn't exist the evaluation will continue with the next candidate. The path names may contain any number of variables in the form '%{variable}' and the values for these variables can be specified when varstack is run to select the desired files. The parsing will start with an empty set of settings and the contents of each file in the list that exists will be merged into this set if settings until all candidates have been read at which point the finalized set of settings is returned.

Note that if the type of a variable is a list then the path containing such a variable in its name will be duplicated for each value in the list. If for example the variable "tags" is a list [mysql, apache] then the evaluation of the path "tags/%{tags}" will result in two paths "tags/mysql.yaml" and "tags/apache.yaml". This feature can only be utilized using the python interface right now and not from the command line. 

The way the data from a new file is merged with the existing data can be controlled by specifying a combination mode. Right now this mode can either be 'merge' or 'replace'. When 'replace' is specified if Varstack encounters a hash or array/list variable the content from previous definitions of this variable is replaced with the content in the new file. This allows one to override variables from previous definitions.
If the mode 'merge' is selected (the default) then content of hash or array/list variables is merged with previous definitions of this variable. This allows for extending previously defined data.
Scalar values like strings, integers, booleans, etc. are always evaluated using the 'replace' mode (a merge doesn't make sense in that case.)

The combination mode can be set by including a hash in the form of
'__combine' => << combination mode >> in the hash or array/list. This allows fine grained control over the evaluation process.

Let's go through a little example that should clarify what's going on during a Varstack run. As a basis we will use the Varstack configuration from above and assume /etc/varstack/stack contains the following files:

/etc/varstack/stack/defaults.yaml
/etc/varstack/stack/environments/development.yaml
/etc/varstack/stack/nodes/supersecure.example.com.yaml

Next let's specify the contents of these files:

#### /etc/varstack/stack/defaults.yaml:
```
---
users:
  anna:
    uid: 500
    groups: [1,2]
    roles: [superadmin]
repos: [epel]
```

#### /etc/varstack/stack/environments/development.yaml:
```
---
users:
  bob:
    uid: 501
    groups: [3]
    roles: [developer]
  anna:
    roles: [developer]
repos: [devrepo]
```

#### /etc/varstack/stack/nodes/supersecure.example.com.yaml:
```
---
users:
  charly:
    uid: 502
    groups: [3]
    roles: [securityadmin]
repos: [securerepo]
```

So now that the definitions are out of the way let's see how Varstack evaluates these files in different ways depending on the input variables and combination mode we specify.

First we look at what happens when we don't specify any variables:

```
# varstack
---
users:
  anna:
    groups: [1, 2]
    roles: [superadmin]
    uid: 500
repos: [epel]
```

As you can see all we get is the contents of the defaults.yaml file. The reason is that since we didn't specify any input variables the defaults file was the only one Varstack could find and evaluate.

Next let's specify an existing environment:

```
# varstack env=development
---
repos: [epel, devrepo]
users:
  anna:
    groups: [1, 2]
    roles: [superadmin, developer]
    uid: 500
  bob:
    groups: [3]
    roles: [developer]
    uid: 501
```

This time Varstack read the default file followed by the development file and merged the new data with the old. The result is the user anna now has two roles 'superadmin' from the defaults file and 'developer' from the development file and user bob was simply added because
there was no previous definition. This example shows how you could define a global user that gets added to all systems and then add individual users for certain environments or individual nodes.

Now let's also define the fqdn variable into the mix:

```
# varstack env=development fqdn=supersecure.example.com
---
repos: [epel,devrepo,securerepo]
users:
  anna:
    groups: [1, 2]
    roles: [superadmin, developer]
    uid: 500
  bob:
    groups: [3]
    roles: [developer]
    uid: 501
  charly:
    groups: [3]
    roles: [securityadmin]
    uid: 502
```

Nothing suprising here. This time the data from the node file got merged into the data as well adding user charly.

The thing is since this system is "supersecure" we don't actually want to inherit any other users and strictly only allow the users defined for this node while at the same time still merging all other data. This is where we are going to modify the supersecure.example.com.yaml file to look like this:

```
---
users:
  __combine: replace
  charly:
    uid: 502
    groups: [3]
    roles: [securityadmin]
repos: [securerepo]
```

Notice the added key '__combine' here which means we want to switch to the combination mode 'replace' for everything below the 'users' key.
Now we call varstack again:

```
# varstack env=development fqdn=supersecure.example.com
---
repos: [epel, devrepo, securerepo]
users:
  charly:
    groups: [3]
    roles: [securityadmin]
    uid: 502
```

This time the 'users' data has been completely replaced *but* the 'repos' key was still merged since we only specified the 'replace' combination mode for the 'users' key.

Finally let's say we want to merge the users but replace the repos which is defined as an array/list instead of a hash. Let's change the file again:

```
---
users:
  charly:
    uid: 502
    groups: [3]
    roles: [securityadmin]
repos: [__combine: replace, securerepo]
```

Notice how we added a '__combine' hash to the list to indicate that we want this array/list to replace the previous data rather than beeing merged. Let's look at the result:

```
# varstack env=development fqdn=supersecure.example.com
---
repos: [securerepo]
users:
  anna:
    groups: [1, 2]
    roles: [superadmin, developer]
    uid: 500
  bob:
    groups: [3]
    roles: [developer]
    uid: 501
  charly:
    groups: [3]
    roles: [securityadmin]
    uid: 502
```

As you can see the 'users' hash was merged this time while now the 'repos' array/list only contains the entry from the node file.



You can also work with encrypted dicts. If a value is PGP encrypted, varstack can decrypt this value if it is encrypted with one of your public keys.

```
---
enc_data: |
  -----BEGIN PGP MESSAGE-----
  
  P1eDjfxWvGFIkKpzgZi7rafqsGSlhXUDvTIcXoopCMABZkycUWQw99TM8QlXrk44
  Svk7CUar...                 ...40aAfYwYS49T7PyfuPnQ0zVVieVjvNO+2
  /eQU3e+ipxKRND8UtSf9jvBIXDcqQUkuubAPHV7WHswb2OoaPm3QFLraPaXoxPR1
  VLglxg==
  =+fch
  -----END PGP MESSAGE-----
```

**Importent!** For this feature you have to install python-gnupg

```
pip install python-gnupg
```

Packageinfo: [https://pythonhosted.org/python-gnupg/](https://pythonhosted.org/python-gnupg/)

Inside this encrypted value, dicts and lists can exist. This will be parsed through varstack, too.

The default gnupgdir is '_$HOME/.gnupg_'. If you want to chose another path, put _gnupghome: PATH_TO_GNUPG_FOLDER_ inside your varstack.yaml config file




