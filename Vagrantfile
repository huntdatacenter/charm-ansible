Vagrant.configure(2) do |config|
  # Development box
  config.vm.define "jujubox" do |dev|
    # Select the box
    dev.vm.box = "bento/ubuntu-16.04"
    # Run playbook
    dev.vm.provision "ansible_local" do |ansible|
      ansible.playbook = "vagrant.yaml"
      ansible.extra_vars = { ansible_python_interpreter: "/usr/bin/python3" }
    end
    dev.vm.provider "virtualbox" do |vbox|
      vbox.memory = 4096
      vbox.cpus = 3
    end
    # Forward SSH agent
    # dev.ssh.forward_agent = true
    # Setup shared project directory
    # dev.vm.synced_folder "../", "/home/vagrant/dev"
  end
  #config.vm.network "forwarded_port", guest: 8080, host: 8080
end
